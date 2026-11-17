"""Routing: decide which agent should handle a message.

Clear signals (a YouTube link, code, a URL, explicit mentions) are handled by rules. Ambiguous
follow-ups use the Groq classifier when a key is configured, otherwise the session's context.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

from core import config, llm
from core.agents.python_exec import looks_like_code
from core.agents.youtube import contains_youtube_url
from core.text_utils import extract_url

logger = logging.getLogger(__name__)

AGENTS = ("youtube", "document", "fetch", "python", "general")

_DOCUMENT_WORDS = re.compile(r"\b(document|doc|pdf|docx|file|upload(?:ed)?|paper|report|resume|cv|contract)\b", re.I)
_VIDEO_WORDS = re.compile(r"\b(video|youtube|transcript|clip|vlog|speaker|presenter|watch)\b", re.I)
_PAGE_WORDS = re.compile(r"\b(page|web ?page|website|site|article|blog post|link)\b", re.I)
_SMALL_TALK = re.compile(
    r"^\s*(hi|hello|hey|thanks|thank you|thx|ok|okay|cool|great|bye|goodbye|good (morning|afternoon|evening))\b[\s!.,]*$",
    re.I,
)


@dataclass
class RouteContext:
    video_title: Optional[str] = None
    document_name: Optional[str] = None
    page_url: Optional[str] = None
    last_agent: Optional[str] = None


@dataclass
class Decision:
    agent: str
    reason: str


def detect(query: str, ctx: RouteContext) -> Decision:
    if contains_youtube_url(query):
        return Decision("youtube", "message contains a YouTube link")
    if looks_like_code(query):
        return Decision("python", "message contains code to run")
    if extract_url(query):
        return Decision("fetch", "message contains a URL")

    mentions = [
        agent for agent, pattern in (("document", _DOCUMENT_WORDS), ("youtube", _VIDEO_WORDS), ("fetch", _PAGE_WORDS))
        if pattern.search(query)
    ]
    loaded = [
        agent for agent, value in (("youtube", ctx.video_title), ("document", ctx.document_name), ("fetch", ctx.page_url))
        if value
    ]
    # Prefer a mentioned agent that has something loaded, then any mentioned agent.
    for agent in mentions:
        if agent in loaded:
            return Decision(agent, f"message refers to the loaded {agent}")
    if len(mentions) == 1 and not loaded:
        return Decision(mentions[0], f"message mentions a {mentions[0]}")

    if not loaded:
        return Decision("general", "no video, document or page in this chat")
    if _SMALL_TALK.match(query):
        return Decision("general", "small talk")
    if config.GROQ_API_KEY:
        decision = _classify_with_llm(query, ctx)
        if decision:
            return decision
    if ctx.last_agent in loaded:
        return Decision(ctx.last_agent, "follow-up to the previous answer")
    return Decision(loaded[0], f"the {loaded[0]} is the active context")


def _classify_with_llm(query: str, ctx: RouteContext) -> Optional[Decision]:
    context_lines = []
    if ctx.video_title:
        context_lines.append(f'- youtube: video "{ctx.video_title}" is loaded')
    if ctx.document_name:
        context_lines.append(f'- document: "{ctx.document_name}" is uploaded')
    if ctx.page_url:
        context_lines.append(f"- fetch: web page {ctx.page_url} is loaded")
    system = (
        "Route the user's message to exactly one agent:\n"
        "youtube = questions about the loaded YouTube video\n"
        "document = questions about the uploaded document\n"
        "fetch = questions about the loaded web page\n"
        "general = anything else (greetings, general knowledge, writing code, unrelated questions)\n"
        "Reply with only the agent name."
    )
    user = (
        "Loaded context:\n" + "\n".join(context_lines)
        + f"\nPrevious agent: {ctx.last_agent or 'none'}\n\nMessage: {query}"
    )
    try:
        label = llm.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=5,
            temperature=0,
            model=config.GROQ_ROUTER_MODEL,
        ).strip().lower()
    except llm.LLMError as e:
        logger.warning("LLM routing failed, falling back to rules: %s", e)
        return None
    label = re.sub(r"[^a-z]", "", label)
    if label in AGENTS and label != "python":
        return Decision(label, "classified by LLM")
    return None
