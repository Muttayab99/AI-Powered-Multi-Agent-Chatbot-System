"""LLM access. Uses Groq when GROQ_API_KEY is set, otherwise a small local model."""
import logging
import threading
from typing import Dict, List, Optional

from core import config

logger = logging.getLogger(__name__)

Message = Dict[str, str]


class LLMError(RuntimeError):
    pass


_groq_client = None
_local_model = None
_local_lock = threading.Lock()


def backend() -> str:
    return "groq" if config.GROQ_API_KEY else "local"


def model_name() -> str:
    return config.GROQ_MODEL if backend() == "groq" else config.LOCAL_LLM_MODEL


def max_context_chars() -> int:
    """Budget of source text per request; the local model needs much smaller prompts."""
    return config.GROQ_MAX_CONTEXT_CHARS if backend() == "groq" else config.LOCAL_MAX_CONTEXT_CHARS


def chat(
    messages: List[Message],
    *,
    max_tokens: int = 800,
    temperature: float = 0.2,
    model: Optional[str] = None,
) -> str:
    if backend() == "groq":
        return _groq_chat(messages, max_tokens, temperature, model or config.GROQ_MODEL)
    return _local_chat(messages, max_tokens)


def _groq_chat(messages: List[Message], max_tokens: int, temperature: float, model: str) -> str:
    global _groq_client
    from groq import Groq

    if _groq_client is None:
        _groq_client = Groq(api_key=config.GROQ_API_KEY, max_retries=4, timeout=90)
    extra = {}
    if model.startswith("openai/gpt-oss"):
        # Reasoning models spend completion tokens thinking before answering; give them headroom
        # and keep the reasoning out of the reply.
        extra = {"reasoning_effort": config.GROQ_REASONING_EFFORT, "include_reasoning": False}
        max_tokens += 1024
    try:
        response = _groq_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            **extra,
        )
    except Exception as e:
        raise LLMError(f"Groq request failed ({model}): {e}") from e
    return (response.choices[0].message.content or "").strip()


def _load_local():
    global _local_model
    if _local_model is None:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading local LLM %s (first use downloads it)...", config.LOCAL_LLM_MODEL)
        tokenizer = AutoTokenizer.from_pretrained(config.LOCAL_LLM_MODEL)
        model = AutoModelForCausalLM.from_pretrained(config.LOCAL_LLM_MODEL)
        model.eval()
        _local_model = (tokenizer, model)
    return _local_model


def _local_chat(messages: List[Message], max_tokens: int) -> str:
    import torch

    with _local_lock:
        try:
            tokenizer, model = _load_local()
            inputs = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
            )
            with torch.no_grad():
                output = model.generate(
                    **inputs,
                    max_new_tokens=min(max_tokens, config.LOCAL_MAX_NEW_TOKENS),
                    do_sample=False,
                    repetition_penalty=1.1,
                    pad_token_id=tokenizer.eos_token_id,
                )
        except Exception as e:
            raise LLMError(f"Local model failed ({config.LOCAL_LLM_MODEL}): {e}") from e
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
