"""Document agent: ingests PDF/DOCX/TXT files and answers, summarizes or analyzes sentiment."""
import base64
import binascii
import logging
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core import config, llm, rag
from core.loaders import UnsupportedFileError, extract_text
from core.text_utils import is_sentiment_request, is_summary_request, sample_text

logger = logging.getLogger(__name__)

AGENT = "document"


@dataclass
class LoadedDocument:
    name: str
    text: str
    index: Any
    chunks: int

    @property
    def label(self) -> str:
        return f'the document "{self.name}"'


_documents: Dict[str, LoadedDocument] = {}
_lock = threading.Lock()


def ingest(session_id: str, filename: str, data: bytes) -> Dict[str, Any]:
    """Extract, chunk and index a file; it becomes the session's active document."""
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        return {"success": False, "agent": AGENT, "reply": f"File is larger than {config.MAX_UPLOAD_MB} MB."}
    if not data:
        return {"success": False, "agent": AGENT, "reply": "The uploaded file is empty."}
    try:
        text = extract_text(filename, data)
    except UnsupportedFileError as e:
        return {"success": False, "agent": AGENT, "reply": str(e)}
    except Exception as e:
        logger.exception("Failed to read %s", filename)
        return {"success": False, "agent": AGENT, "reply": f"Couldn't read '{filename}': {e}"}
    if len(text) < 20:
        return {
            "success": False,
            "agent": AGENT,
            "reply": f"'{filename}' contains no extractable text (scanned PDFs need OCR first).",
        }

    index = rag.build_index(text)
    document = LoadedDocument(filename, text, index, len(index))
    with _lock:
        _documents[session_id] = document
    return {
        "success": True,
        "agent": AGENT,
        "reply": f"Loaded '{filename}' ({len(text):,} characters, {document.chunks} chunks). Ask me anything about it.",
        "document_name": filename,
        "characters": len(text),
        "chunks": document.chunks,
    }


def analyze_sentiment(document: LoadedDocument, question: str) -> str:
    excerpt = sample_text(document.text, llm.max_context_chars())
    return llm.chat(
        [
            {"role": "system", "content": "You analyze the sentiment and tone of documents accurately."},
            {
                "role": "user",
                "content": (
                    f"Analyze the overall sentiment of {document.label}. Start with one line "
                    "'Overall sentiment: Positive | Negative | Neutral | Mixed', then give 2-4 bullet points "
                    f"citing evidence from the text. User request: {question}\n\nText:\n{excerpt}"
                ),
            },
        ],
        max_tokens=500,
    )


def handle(session_id: str, query: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    document = _documents.get(session_id)
    if not document:
        return {
            "success": False,
            "agent": AGENT,
            "reply": "No document is loaded for this chat yet. Upload a PDF, DOCX or TXT file first.",
        }
    if is_sentiment_request(query):
        reply = analyze_sentiment(document, query)
    elif is_summary_request(query):
        reply = rag.summarize(document.text, document.label, focus=query)
    else:
        reply = rag.answer_from_passages(query, rag.retrieve(document.index, query), document.label, history)
    return {"success": True, "agent": AGENT, "reply": reply, "document_name": document.name}


def upload_document(session_id: str, filename: str, content_base64: str) -> Dict[str, Any]:
    """Load a base64-encoded PDF/DOCX/TXT/MD file as the session's active document."""
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError):
        return {"success": False, "agent": AGENT, "reply": "content_base64 is not valid base64."}
    return ingest(session_id, filename, data)


def info(session_id: str) -> Dict[str, Any]:
    """Describe the session's active document."""
    document = _documents.get(session_id)
    if not document:
        return {"loaded": False}
    return {"loaded": True, "document_name": document.name, "characters": len(document.text), "chunks": document.chunks}


def clear_session(session_id: str) -> Dict[str, Any]:
    """Drop the session's document."""
    with _lock:
        _documents.pop(session_id, None)
    return {"success": True}


def health() -> Dict[str, Any]:
    return {"status": "healthy", "agent": AGENT, "loaded_documents": len(_documents)}
