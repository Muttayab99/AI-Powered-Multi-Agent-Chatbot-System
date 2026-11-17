"""YouTube agent: fetches a video's transcript, indexes it and answers questions about it."""
import html
import json
import logging
import re
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from core import rag
from core.text_utils import is_summary_request, strip_urls

logger = logging.getLogger(__name__)

AGENT = "youtube"
PREFERRED_LANGUAGES = ["en", "en-US", "en-GB", "en-orig"]

_VIDEO_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.|music\.)?"
    r"(?:youtube\.com/(?:watch\?(?:[^\s#]*?&)?v=|shorts/|embed/|live/|v/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})",
    re.IGNORECASE,
)


class TranscriptUnavailable(RuntimeError):
    pass


@dataclass
class Video:
    video_id: str
    title: str
    author: str
    transcript: str
    index: Any

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def label(self) -> str:
        by = f" by {self.author}" if self.author else ""
        return f'the YouTube video "{self.title}"{by} (from its transcript)'


_videos: Dict[str, Video] = {}
_session_video: Dict[str, str] = {}
_lock = threading.Lock()
_video_locks: Dict[str, threading.Lock] = {}


def extract_video_id(text: str) -> Optional[str]:
    match = _VIDEO_URL_RE.search(text or "")
    return match.group(1) if match else None


def contains_youtube_url(text: str) -> bool:
    return extract_video_id(text) is not None


def _clean_transcript(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\[(?:music|applause|laughter|inaudible)\]", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def fetch_metadata(video_id: str) -> Tuple[str, str]:
    try:
        response = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=10,
        )
        if response.ok:
            data = response.json()
            return data.get("title") or "Untitled video", data.get("author_name") or ""
    except Exception as e:
        logger.warning("oEmbed lookup failed for %s: %s", video_id, e)
    return "YouTube video", ""


def _transcript_via_api(video_id: str) -> str:
    from youtube_transcript_api import NoTranscriptFound, YouTubeTranscriptApi

    transcripts = YouTubeTranscriptApi().list(video_id)
    try:
        transcript = transcripts.find_transcript(PREFERRED_LANGUAGES)
    except NoTranscriptFound:
        available = list(transcripts)
        if not available:
            raise
        transcript = available[0]
        if transcript.is_translatable:
            try:
                transcript = transcript.translate("en")
            except Exception:
                transcript = available[0]
    return " ".join(snippet.text for snippet in transcript.fetch())


def _parse_caption_file(body: str) -> str:
    try:
        data = json.loads(body)
        return " ".join(
            seg.get("utf8", "") for event in data.get("events", []) for seg in event.get("segs", []) or []
        )
    except json.JSONDecodeError:
        pass
    lines = []
    for line in body.splitlines():
        line = line.strip()
        if not line or "-->" in line or line.isdigit() or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        lines.append(re.sub(r"<[^>]+>", "", line))
    # Auto-generated VTT repeats each line while it scrolls; drop consecutive duplicates.
    deduped = [line for i, line in enumerate(lines) if i == 0 or line != lines[i - 1]]
    return " ".join(deduped)


def _pick_english(tracks: Dict[str, Any]) -> Optional[str]:
    for language in PREFERRED_LANGUAGES:
        if language in tracks:
            return language
    return next((language for language in tracks if language.startswith("en")), None)


def _transcript_via_ytdlp(video_id: str) -> str:
    import yt_dlp

    options = {"skip_download": True, "quiet": True, "no_warnings": True, "noprogress": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

    manual = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat"}
    automatic = info.get("automatic_captions") or {}
    # English manual captions first, then English auto captions, then any manual track.
    choices = [
        (manual, _pick_english(manual)),
        (automatic, _pick_english(automatic)),
        (manual, next(iter(manual), None)),
    ]
    for tracks, language in choices:
        if not language:
            continue
        formats = sorted(tracks[language], key=lambda f: {"json3": 0, "vtt": 1}.get(f.get("ext"), 2))
        for fmt in formats:
            response = requests.get(fmt["url"], timeout=20)
            if response.ok and response.text.strip():
                text = _parse_caption_file(response.text)
                if text.strip():
                    return text
    raise TranscriptUnavailable("yt-dlp found no caption tracks")


def fetch_transcript(video_id: str) -> str:
    errors = []
    for method in (_transcript_via_api, _transcript_via_ytdlp):
        try:
            text = _clean_transcript(method(video_id))
            if text:
                return text
            errors.append(f"{method.__name__}: empty transcript")
        except Exception as e:
            logger.warning("%s failed for %s: %s", method.__name__, video_id, e)
            errors.append(f"{method.__name__}: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}")
    raise TranscriptUnavailable(
        "I couldn't get a transcript for this video. It may have captions disabled, be private, "
        "age-restricted or region-locked, or YouTube may be rate-limiting this network.\n\nDetails: "
        + "; ".join(errors)
    )


def load_video(video_id: str) -> Video:
    """Fetch and index a video once; later calls (from any session) reuse the cached index."""
    with _lock:
        if video_id in _videos:
            return _videos[video_id]
        video_lock = _video_locks.setdefault(video_id, threading.Lock())
    with video_lock:
        if video_id in _videos:
            return _videos[video_id]
        title, author = fetch_metadata(video_id)
        transcript = fetch_transcript(video_id)
        video = Video(video_id, title, author, transcript, rag.build_index(transcript))
        with _lock:
            _videos[video_id] = video
        logger.info("Indexed video %s (%s chars)", video_id, len(transcript))
        return video


def handle(
    session_id: str,
    query: str,
    video_url: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    video_id = extract_video_id(query) or extract_video_id(video_url or "") or _session_video.get(session_id)
    if not video_id:
        return {
            "success": False,
            "agent": AGENT,
            "reply": "Please share a YouTube link (e.g. https://www.youtube.com/watch?v=...) and I'll answer questions about the video.",
        }
    try:
        video = load_video(video_id)
    except TranscriptUnavailable as e:
        return {"success": False, "agent": AGENT, "reply": str(e)}

    _session_video[session_id] = video_id
    question = strip_urls(query)
    if len(question.split()) <= 2 or is_summary_request(question):
        reply = rag.summarize(video.transcript, video.label, focus=question if len(question.split()) > 2 else None)
    else:
        passages = rag.retrieve(video.index, question)
        reply = rag.answer_from_passages(question, passages, video.label, history)
    return {
        "success": True,
        "agent": AGENT,
        "reply": reply,
        "video_id": video.video_id,
        "video_url": video.url,
        "video_title": video.title,
    }


def list_videos() -> Dict[str, Any]:
    """List videos whose transcripts are indexed."""
    with _lock:
        videos = [{"video_id": v.video_id, "title": v.title, "author": v.author} for v in _videos.values()]
    return {"success": True, "videos": videos}


def clear_session(session_id: str) -> Dict[str, Any]:
    """Forget which video this session is talking about (the cached index is kept for reuse)."""
    _session_video.pop(session_id, None)
    return {"success": True}


def health() -> Dict[str, Any]:
    return {"status": "healthy", "agent": AGENT, "indexed_videos": len(_videos)}
