"""End-to-end tests of the unified gateway with the LLM stubbed out (retrieval and execution are real)."""
import pytest
from fastapi.testclient import TestClient

from core import intent, llm


def fake_chat(messages, **kwargs):
    """Echo the final prompt so tests can see which context reached the model."""
    return "LLM:" + messages[-1]["content"]


@pytest.fixture(scope="module")
def client():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(llm, "chat", fake_chat)
    patcher.setattr(intent.config, "GROQ_API_KEY", "")
    from servers.unified import app

    with TestClient(app) as test_client:
        yield test_client
    patcher.undo()


def chat(client, session_id, query):
    response = client.post("/chat", json={"session_id": session_id, "query": query})
    assert response.status_code == 200, response.text
    return response.json()


def test_root_and_health(client):
    # /api, not /: once frontend/dist is built, / serves the web UI instead.
    assert "python" in client.get("/api").json()["available_agents"]
    health = client.get("/health").json()
    assert health["mode"] == "unified"
    assert all(agent["status"] == "healthy" for agent in health["agents"].values())


def test_python_agent(client):
    result = chat(client, "py", "Execute this Python code:\nnums = [3, 1, 2]\nprint(sorted(nums))")
    assert result["agent"] == "python"
    assert result["success"]
    assert "[1, 2, 3]" in result["reply"]


def test_general_agent(client):
    result = chat(client, "gen", "What is the capital of France?")
    assert result["agent"] == "general"
    assert "capital of France" in result["reply"]


def test_document_flow(client):
    text = ("Intro filler sentence about nothing in particular. " * 60
            + "The project budget for 2025 is 42 million dollars. "
            + "Closing filler sentence about other topics. " * 60)
    upload = client.post("/upload", data={"session_id": "doc"}, files={"file": ("report.txt", text.encode(), "text/plain")})
    assert upload.status_code == 200
    assert upload.json()["success"], upload.json()

    answer = chat(client, "doc", "What is the project budget?")
    assert answer["agent"] == "document"
    assert "42 million" in answer["reply"]  # the relevant chunk was retrieved and sent to the LLM

    sentiment = chat(client, "doc", "What is the sentiment of the document?")
    assert sentiment["agent"] == "document" and "Overall sentiment" in sentiment["reply"]

    session = client.get("/sessions/doc").json()
    assert session["document_name"] == "report.txt"
    assert client.delete("/sessions/doc").json()["success"]
    assert chat(client, "doc", "what does the document say?")["success"] is False


def test_document_without_upload(client):
    result = chat(client, "nodoc", "summarize the document")
    assert result["agent"] == "document"
    assert not result["success"]
    assert "Upload" in result["reply"]


def test_bad_upload(client):
    response = client.post("/upload", data={"session_id": "bad"}, files={"file": ("x.exe", b"MZ...", "application/octet-stream")})
    assert response.json()["success"] is False
    assert "Unsupported" in response.json()["reply"]


def test_fetch_blocks_localhost(client):
    result = chat(client, "f", "fetch http://127.0.0.1:8000/health")
    assert result["agent"] == "fetch"
    assert not result["success"]
    assert "private or local" in result["reply"]


def test_youtube_needs_link(client):
    result = chat(client, "yt", "summarize the youtube video")
    assert result["agent"] == "youtube"
    assert not result["success"]
    assert "YouTube link" in result["reply"]


def test_api_prefix_matches_legacy_paths(client):
    info = client.get("/api").json()
    assert "python" in info["available_agents"] and info["max_upload_mb"] > 0
    assert client.get("/api/health").json()["mode"] == "unified"
    result = client.post("/api/chat", json={"session_id": "api", "query": "What is the capital of France?"}).json()
    assert result["agent"] == "general"
    assert client.get("/api/sessions/api").status_code == 200
    assert client.get("/api/sessions/never-created").status_code == 404


def test_cors_allows_dev_origin(client):
    preflight = client.options("/api/chat", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_serves_built_frontend(tmp_path, monkeypatch):
    from core import config
    from servers.gateway import create_app

    (tmp_path / "index.html").write_text("<!doctype html><title>Glass UI</title>")
    (tmp_path / "app.js").write_text("console.log('ok')")
    monkeypatch.setattr(config, "FRONTEND_DIST", tmp_path)
    with TestClient(create_app("local")) as frontend_client:
        assert "Glass UI" in frontend_client.get("/").text
        assert frontend_client.get("/app.js").status_code == 200
        assert frontend_client.get("/api/health").json()["mode"] == "unified"
        assert frontend_client.get("/docs").status_code == 200
