"""Thin, defensive client for an OpenAI-compatible chat API (Featherless AI).

* The API key stays on the server and is never logged or returned.
* Anything sent out is minimised and redacted (emails, phone numbers, Aadhaar/PAN-like numbers).
* Anything coming back is treated as untrusted text: callers either render it as plain text or validate it strictly.
"""
import json
import logging
import re

import httpx2 as httpx

from app.config import get_settings
from app.core.errors import AppError

log = logging.getLogger("sims.ai")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\s-]?){10,13}(?!\d)")
_AADHAAR = re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")


class AIDisabled(AppError):
    status, code = 503, "ai_disabled"

    def __init__(self) -> None:
        super().__init__("AI assistance is not enabled for this installation.")


class AIUnavailable(AppError):
    status, code = 502, "ai_unavailable"

    def __init__(self, message: str = "The AI service is temporarily unavailable. Please try again.") -> None:
        super().__init__(message)


def redact(text: str) -> str:
    """Mask personal identifiers before text leaves the system."""
    text = _EMAIL.sub("[email]", text)
    text = _AADHAAR.sub("[id-number]", text)
    text = _PAN.sub("[id-number]", text)
    return _PHONE.sub("[phone]", text)


def enabled() -> bool:
    s = get_settings()
    return bool(s.ai_enabled and s.ai_api_key)


# Replaceable in tests (httpx.MockTransport) so no network is ever needed.
_transport: httpx.BaseTransport | None = None


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


def chat(system: str, user: str, *, max_tokens: int | None = None, temperature: float = 0.2, json_mode: bool = False) -> str:
    s = get_settings()
    if not enabled():
        raise AIDisabled()
    payload: dict = {
        "model": s.ai_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": min(max_tokens or s.ai_max_tokens, s.ai_max_tokens),
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        with httpx.Client(base_url=s.ai_base_url, timeout=s.ai_timeout_seconds, transport=_transport) as client:
            r = client.post("/chat/completions", json=payload, headers={"Authorization": f"Bearer {s.ai_api_key}"})
    except httpx.HTTPError as exc:
        log.warning("AI request failed: %s", type(exc).__name__)
        raise AIUnavailable() from None
    if r.status_code == 429:
        raise AIUnavailable("The AI service is busy. Please try again in a moment.")
    if r.status_code >= 400:
        log.warning("AI service returned %s", r.status_code)
        raise AIUnavailable()
    try:
        content = r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError, TypeError):
        raise AIUnavailable("The AI service returned an unexpected response.") from None
    return (content or "").strip()


def chat_json(system: str, user: str, **kw) -> dict:
    """Ask for a JSON object; tolerate code fences and surrounding prose, reject anything that is not an object."""
    raw = chat(system, user, json_mode=True, **kw)
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise AIUnavailable("The AI service did not return a usable answer. Please rephrase and try again.")
    return data
