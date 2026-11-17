"""Shared retrieval-augmented generation helpers: chunking, FAISS indexes, grounded answers, summaries."""
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from core import config, llm

logger = logging.getLogger(__name__)

_embeddings = None
_embeddings_lock = threading.Lock()


def embeddings():
    global _embeddings
    with _embeddings_lock:
        if _embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings

            logger.info("Loading embedding model %s...", config.EMBEDDING_MODEL)
            _embeddings = HuggingFaceEmbeddings(
                model_name=config.EMBEDDING_MODEL,
                encode_kwargs={"normalize_embeddings": True},
            )
    return _embeddings


def split_text(text: str, chunk_size: int = config.CHUNK_SIZE, overlap: int = config.CHUNK_OVERLAP) -> List[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return [chunk for chunk in splitter.split_text(text) if chunk.strip()]


class VectorIndex:
    """In-memory FAISS index over text chunks (cosine similarity via normalized embeddings)."""

    def __init__(self, chunks: List[str]):
        import faiss
        import numpy as np

        vectors = np.asarray(embeddings().embed_documents(chunks), dtype="float32")
        self.chunks = chunks
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query: str, k: int) -> List[str]:
        import numpy as np

        vector = np.asarray([embeddings().embed_query(query)], dtype="float32")
        _, ids = self.index.search(vector, min(k, len(self.chunks)))
        return [self.chunks[i] for i in ids[0] if i >= 0]


def build_index(text: str) -> VectorIndex:
    chunks = split_text(text)
    if not chunks:
        raise ValueError("No text to index.")
    return VectorIndex(chunks)


def retrieve(index: VectorIndex, query: str, k: int = config.RETRIEVAL_K) -> List[str]:
    return index.search(query, k)


def history_messages(history: Optional[List[Dict[str, Any]]], limit: int = 6) -> List[Dict[str, str]]:
    """Recent conversation turns as chat messages, trimmed so they never crowd out the sources."""
    messages = []
    for turn in (history or [])[-limit:]:
        role = turn.get("role")
        content = str(turn.get("content", ""))[:1500]
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    return messages


def answer_from_passages(
    question: str,
    passages: List[str],
    source: str,
    history: Optional[List[Dict[str, Any]]] = None,
) -> str:
    budget = llm.max_context_chars()
    context, used = [], 0
    for i, passage in enumerate(passages, 1):
        if used + len(passage) > budget:
            break
        context.append(f"[Excerpt {i}]\n{passage}")
        used += len(passage)
    system = (
        f"You answer questions about {source}. Use only the excerpts provided. "
        "If the excerpts do not contain the answer, say so plainly instead of guessing. "
        "Be concise and specific; use bullet points for lists. Do not add citation markers."
    )
    user = "Excerpts:\n\n" + "\n\n".join(context) + f"\n\nQuestion: {question}"
    messages = [{"role": "system", "content": system}, *history_messages(history), {"role": "user", "content": user}]
    return _strip_citations(llm.chat(messages, max_tokens=700))


def _strip_citations(text: str) -> str:
    """Remove model-inserted citation markers such as 【Excerpt 1†6】 or [Excerpt 2]."""
    text = re.sub(r"\s*【[^】]*】", "", text)
    return re.sub(r"\s*\[Excerpt \d+[^\]]*\]", "", text)


def summarize(text: str, source: str, focus: Optional[str] = None) -> str:
    """Summarize text of any length; long text is summarized in parts and the notes are combined."""
    budget = llm.max_context_chars()
    instruction = f"Summarize {source}."
    if focus:
        instruction += f" The user asked: \"{focus}\" - address that directly."
    instruction += " Start with a one-sentence overview, then list the key points as bullets."

    if len(text) <= budget:
        return _strip_citations(llm.chat(
            [
                {"role": "system", "content": "You write accurate, well-structured summaries."},
                {"role": "user", "content": f"{instruction}\n\nText:\n{text}"},
            ],
            max_tokens=700,
        ))

    parts = split_text(text, chunk_size=budget, overlap=200)
    max_parts = 4 if llm.backend() == "groq" else 3
    if len(parts) > max_parts:
        step = len(parts) / max_parts
        parts = [parts[int(i * step)] for i in range(max_parts)]
    def take_notes(numbered_part):
        i, part = numbered_part
        return llm.chat(
            [
                {"role": "system", "content": "You extract the important points from text."},
                {"role": "user", "content": f"Write concise bullet notes of the key points in part {i} of {len(parts)} of {source}:\n\n{part}"},
            ],
            max_tokens=400,
            # Groq rate limits are per model, so note-taking uses the small model's separate quota.
            model=config.GROQ_ROUTER_MODEL if llm.backend() == "groq" else None,
        )

    # Groq calls run in parallel; the local model is single-threaded anyway.
    workers = 3 if llm.backend() == "groq" else 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        notes = list(pool.map(take_notes, enumerate(parts, 1)))
    combined = "\n\n".join(notes)[:budget]
    return _strip_citations(llm.chat(
        [
            {"role": "system", "content": "You write accurate, well-structured summaries."},
            {"role": "user", "content": f"{instruction}\n\nThese are notes taken from consecutive parts of it:\n\n{combined}"},
        ],
        max_tokens=700,
    ))
