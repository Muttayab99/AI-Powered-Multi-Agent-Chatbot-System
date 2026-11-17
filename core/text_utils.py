"""Small text helpers shared by the router and the agents."""
import re
from typing import Optional

_TRAILING_PUNCT = ".,;:!?)]}>'\""

_HTTP_URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
_WWW_URL_RE = re.compile(r"\bwww\.[^\s<>\"'`]+", re.IGNORECASE)
# Bare domains are only recognised for common TLDs, so "file.py" or "e.g." never match.
_BARE_DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com|org|net|edu|gov|io|ai|dev|co|uk|de|fr|in|pk|info|app|me|tech|news|blog|wiki|us|ca|au)"
    r"(?:/[^\s<>\"'`]*)?(?=$|[\s,;!?)])",
    re.IGNORECASE,
)

_SUMMARY_RE = re.compile(
    r"\b(summar\w*|overview|tl;?dr|gist|recap|key (?:points|takeaways|ideas)|main (?:points|ideas|topics|takeaways)"
    r"|what(?:'s| is) (?:this|it|the)(?: (?:video|document|doc|file|pdf|page|article|site|website))? about)\b",
    re.IGNORECASE,
)
_SENTIMENT_RE = re.compile(
    r"\b(sentiment|tone|mood|emotion\w*|attitude|positive or negative|negative or positive)\b",
    re.IGNORECASE,
)


def extract_url(text: str) -> Optional[str]:
    """Return the first URL-like token in text, normalised to start with http(s)://."""
    for pattern in (_HTTP_URL_RE, _WWW_URL_RE, _BARE_DOMAIN_RE):
        match = pattern.search(text or "")
        if match:
            url = match.group(0).rstrip(_TRAILING_PUNCT)
            if not url.lower().startswith(("http://", "https://")):
                url = "https://" + url
            return url
    return None


def strip_urls(text: str) -> str:
    for pattern in (_HTTP_URL_RE, _WWW_URL_RE, _BARE_DOMAIN_RE):
        text = pattern.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_summary_request(text: str) -> bool:
    return bool(_SUMMARY_RE.search(text or ""))


def is_sentiment_request(text: str) -> bool:
    return bool(_SENTIMENT_RE.search(text or ""))


def sample_text(text: str, limit: int) -> str:
    """Fit text into limit chars by keeping evenly spaced slices from start, middle and end."""
    if len(text) <= limit:
        return text
    part = limit // 3
    middle = len(text) // 2 - part // 2
    return "\n[...]\n".join([text[:part], text[middle:middle + part], text[-part:]])
