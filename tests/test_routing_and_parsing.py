import pytest

from core import intent, loaders
from core.agents import fetch, youtube
from core.text_utils import extract_url, is_sentiment_request, is_summary_request, strip_urls

NO_CONTEXT = intent.RouteContext()


@pytest.fixture(autouse=True)
def no_groq(monkeypatch):
    monkeypatch.setattr(intent.config, "GROQ_API_KEY", "")


@pytest.mark.parametrize(
    "query,ctx,expected",
    [
        ("Summarize https://www.youtube.com/watch?v=dQw4w9WgXcQ", NO_CONTEXT, "youtube"),
        ("what is this about? https://youtu.be/dQw4w9WgXcQ", NO_CONTEXT, "youtube"),
        ("Fetch and summarize https://example.com/article", NO_CONTEXT, "fetch"),
        ("summarize example.org/news", NO_CONTEXT, "fetch"),
        ("Execute this Python code:\nprint(1)", NO_CONTEXT, "python"),
        ("```python\nprint(1)\n```", NO_CONTEXT, "python"),
        ("hello there", NO_CONTEXT, "general"),
        ("What is the capital of France?", NO_CONTEXT, "general"),
        ("what is the summary of the document?", NO_CONTEXT, "document"),
        ("what are the main topics?", intent.RouteContext(video_title="V"), "youtube"),
        ("what is the sentiment?", intent.RouteContext(document_name="a.pdf"), "document"),
        ("what does the document say about pricing?",
         intent.RouteContext(video_title="V", document_name="a.pdf", last_agent="youtube"), "document"),
        ("and the conclusion?",
         intent.RouteContext(video_title="V", document_name="a.pdf", last_agent="document"), "document"),
        ("thanks!", intent.RouteContext(document_name="a.pdf"), "general"),
    ],
)
def test_routing(query, ctx, expected):
    assert intent.detect(query, ctx).agent == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?feature=share&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://example.com/watch?v=dQw4w9WgXcQ", None),
        ("no link here", None),
    ],
)
def test_extract_video_id(text, expected):
    assert youtube.extract_video_id(text) == expected


def test_parse_caption_formats():
    json3 = '{"events": [{"segs": [{"utf8": "hello "}, {"utf8": "world"}]}, {"tStartMs": 1}]}'
    assert youtube._parse_caption_file(json3).split() == ["hello", "world"]
    vtt = "WEBVTT\nKind: captions\n\n00:00:00.000 --> 00:00:01.000\nhello <c>there</c>\n\n00:00:01.000 --> 00:00:02.000\nhello there\nnext line\n"
    assert youtube._parse_caption_file(vtt) == "hello there next line"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("see https://example.com/a?b=1.", "https://example.com/a?b=1"),
        ("(https://example.com/x)", "https://example.com/x"),
        ("visit www.python.org today", "https://www.python.org"),
        ("read en.wikipedia.org/wiki/Python please", "https://en.wikipedia.org/wiki/Python"),
        ("open file.py and e.g. config.json", None),
    ],
)
def test_extract_url(text, expected):
    assert extract_url(text) == expected


def test_strip_urls_and_request_detection():
    assert strip_urls("Summarize https://x.com/a now") == "Summarize now"
    assert is_summary_request("give me the key points")
    assert is_summary_request("What is this video about?")
    assert not is_summary_request("who is the speaker?")
    assert is_sentiment_request("what's the overall tone?")


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:8000/", "http://localhost/", "http://192.168.1.1/", "http://169.254.169.254/latest/meta-data",
     "http://10.0.0.5/", "file:///etc/passwd", "ftp://example.com/x", "http://[::1]/"],
)
def test_ssrf_protection(url, monkeypatch):
    monkeypatch.setattr(fetch.config, "ALLOW_PRIVATE_URLS", False)
    with pytest.raises(fetch.FetchError):
        fetch.check_url_allowed(url)


def test_extract_html_prefers_article():
    html = b"""<html><head><title>My Post</title><script>var x=1;</script></head><body>
    <nav>Home About Contact</nav><article><h1>Heading</h1><p>""" + b"Real content sentence. " * 30 + b"""</p></article>
    <footer>Copyright</footer></body></html>"""
    title, text = fetch.extract_html(html)
    assert title == "My Post"
    assert "Real content sentence." in text
    assert "Home About" not in text and "var x" not in text and "Copyright" not in text


def _minimal_pdf(text: str) -> bytes:
    stream = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def test_loaders():
    import io

    from docx import Document

    assert "Hello PDF world" in loaders.extract_text("a.pdf", _minimal_pdf("Hello PDF world"))
    doc = Document()
    doc.add_paragraph("Paragraph one")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "A", "B"
    buffer = io.BytesIO()
    doc.save(buffer)
    text = loaders.extract_text("a.docx", buffer.getvalue())
    assert "Paragraph one" in text and "A | B" in text
    assert loaders.extract_text("a.txt", "café".encode("utf-8")) == "café"
    assert loaders.extract_text("a.txt", "café".encode("latin-1")) == "café"
    with pytest.raises(loaders.UnsupportedFileError):
        loaders.extract_text("a.exe", b"MZ")
