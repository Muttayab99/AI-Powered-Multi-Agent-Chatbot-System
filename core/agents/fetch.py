"""Fetch agent: downloads a web page safely, extracts readable text, and summarizes or answers questions."""
import ipaddress
import logging
import re
import socket
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

from core import config, llm, rag
from core.loaders import decode_text, pdf_text
from core.text_utils import extract_url, is_summary_request, strip_urls

logger = logging.getLogger(__name__)

AGENT = "fetch"
MAX_REDIRECTS = 5
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,text/plain,application/json,application/pdf;q=0.9,*/*;q=0.5",
    "Accept-Language": "en-US,en;q=0.8",
}
# Words that, on their own, just mean "get this page" rather than asking a question about it.
_FETCH_ONLY_WORDS = {"fetch", "get", "open", "read", "load", "visit", "browse", "check", "this", "the", "page",
                     "url", "link", "website", "site", "and", "please", "out", "it", "for", "me", "from", "of"}
_NOISE_TAGS = ["script", "style", "noscript", "template", "svg", "iframe", "form", "nav", "footer",
               "aside", "button", "select", "input"]


class FetchError(RuntimeError):
    pass


@dataclass
class Page:
    url: str
    requested_url: str
    title: str
    text: str
    _index: Any = field(default=None, repr=False)

    @property
    def label(self) -> str:
        return f'the web page "{self.title}" ({self.url})'

    def index(self):
        if self._index is None:
            self._index = rag.build_index(self.text)
        return self._index


_pages: Dict[str, Page] = {}
_lock = threading.Lock()


def check_url_allowed(url: str) -> None:
    """Reject non-http(s) URLs and hosts resolving to private, loopback or link-local addresses (SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError(f"Only http and https URLs are supported (got '{parsed.scheme or 'none'}').")
    if not parsed.hostname:
        raise FetchError(f"'{url}' is not a valid URL.")
    if config.ALLOW_PRIVATE_URLS:
        return
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except socket.gaierror:
        raise FetchError(f"Couldn't resolve the host '{parsed.hostname}'. Check the URL.")
    for address in addresses:
        if not ipaddress.ip_address(address.split("%")[0]).is_global:
            raise FetchError(f"Refusing to fetch '{parsed.hostname}': it points to a private or local address.")


def _read_limited(response: requests.Response) -> bytes:
    limit = config.FETCH_MAX_MB * 1024 * 1024
    data = bytearray()
    for chunk in response.iter_content(64 * 1024):
        data.extend(chunk)
        if len(data) > limit:
            raise FetchError(f"The page is larger than {config.FETCH_MAX_MB} MB.")
    return bytes(data)


def extract_html(raw: bytes) -> Tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        og = soup.find("meta", property="og:title")
        title = (og.get("content") or "").strip() if og else ""
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    body = soup.body or soup
    root = soup.find("article") or soup.find("main") or body
    text = root.get_text("\n", strip=True)
    if root is not body and len(text) < 300:
        text = body.get_text("\n", strip=True)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return title, text.strip()


def fetch_page(url: str) -> Page:
    session = requests.Session()
    current = url
    try:
        for _ in range(MAX_REDIRECTS + 1):
            check_url_allowed(current)
            response = session.get(
                current, headers=HEADERS, timeout=(10, config.FETCH_TIMEOUT), allow_redirects=False, stream=True
            )
            if response.is_redirect and response.headers.get("Location"):
                current = urljoin(current, response.headers["Location"])
                response.close()
                continue
            break
        else:
            raise FetchError("Too many redirects.")

        if response.status_code >= 400:
            raise FetchError(f"The site returned HTTP {response.status_code} for {current}.")
        raw = _read_limited(response)
    except requests.exceptions.Timeout:
        raise FetchError(f"Timed out fetching {current}.")
    except requests.exceptions.SSLError:
        raise FetchError(f"SSL certificate error for {current}.")
    except requests.exceptions.ConnectionError:
        raise FetchError(f"Couldn't connect to {urlparse(current).hostname}.")

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" in content_type or raw[:5] == b"%PDF-":
        title, text = current.rsplit("/", 1)[-1] or current, pdf_text(raw)
    elif "html" in content_type or "xml" in content_type or raw.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
        title, text = extract_html(raw)
    elif content_type.startswith("text/") or "json" in content_type or not content_type:
        title, text = current, decode_text(raw)
    else:
        raise FetchError(f"Can't read content of type '{content_type}'.")

    if len(text) < 50:
        raise FetchError(
            "The page has almost no readable text. It may be rendered with JavaScript, require a login, "
            "or block automated access."
        )
    return Page(url=current, requested_url=url, title=title or current, text=text)


def _is_fetch_only(question: str) -> bool:
    words = re.findall(r"[a-z']+", question.lower())
    return all(word in _FETCH_ONLY_WORDS for word in words)


def handle(
    session_id: str,
    query: str,
    url: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    url = extract_url(query) or url
    cached = _pages.get(session_id)
    if not url and cached:
        url = cached.url
    if not url:
        return {"success": False, "agent": AGENT, "reply": "Please include the URL of the page you want me to read."}

    if cached and url in (cached.url, cached.requested_url):
        page = cached
    else:
        try:
            page = fetch_page(url)
        except FetchError as e:
            return {"success": False, "agent": AGENT, "reply": str(e)}
        with _lock:
            _pages[session_id] = page

    question = strip_urls(query)
    if _is_fetch_only(question) or is_summary_request(question):
        reply = rag.summarize(page.text, page.label, focus=None if _is_fetch_only(question) else question)
    elif len(page.text) <= llm.max_context_chars():
        reply = rag.answer_from_passages(question, [page.text], page.label, history)
    else:
        reply = rag.answer_from_passages(question, rag.retrieve(page.index(), question), page.label, history)
    return {"success": True, "agent": AGENT, "reply": reply, "url": page.url, "page_title": page.title}


def clear_session(session_id: str) -> Dict[str, Any]:
    """Drop the session's cached page."""
    with _lock:
        _pages.pop(session_id, None)
    return {"success": True}


def health() -> Dict[str, Any]:
    return {"status": "healthy", "agent": AGENT, "cached_pages": len(_pages)}
