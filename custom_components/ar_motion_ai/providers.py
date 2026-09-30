"""Direct AI vision providers for AR Motion AI (no separate HA integration needed)."""
from __future__ import annotations

import base64
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    PROVIDER_ANTHROPIC,
    PROVIDER_COMPATIBLE,
    PROVIDER_GEMINI,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
)

_LOGGER = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
OPENAI_URL = "https://api.openai.com/v1"
ANTHROPIC_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"

MAX_TOKENS = 300


class ProviderError(HomeAssistantError):
    """Friendly provider error. `code` maps to a config-flow error key."""

    def __init__(self, message: str, code: str = "unknown") -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------- errors
def _friendly(provider: str, status: int, body: Any) -> ProviderError:
    """Turn provider HTTP errors into something readable on a dashboard."""
    raw = ""
    err_type = ""
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict):
            raw = str(err.get("message") or err.get("status") or err)
            err_type = str(err.get("code") or err.get("type") or err.get("status") or "")
        else:
            raw = str(err)
    else:
        raw = str(body)[:300]
    low = f"{raw} {err_type}".lower()
    label = PROVIDER_LABELS.get(provider, provider)

    if status in (401, 403) or "invalid api key" in low or "api key not valid" in low or "incorrect api key" in low:
        return ProviderError(f"{label}: API key rejected — check the key", "invalid_auth")
    if "insufficient_quota" in low or "credit balance" in low or "billing" in low or "insufficient funds" in low:
        return ProviderError(
            f"{label}: account has no credit — add billing on the provider site or switch provider",
            "no_credit",
        )
    if status == 429 or "resource_exhausted" in low or "rate limit" in low:
        return ProviderError(f"{label}: rate limit / free quota used up — try again later", "rate_limited")
    if status == 404 or "not found" in low or "does not exist" in low:
        return ProviderError(f"{label}: model not found — pick another model ({raw})", "bad_model")
    return ProviderError(f"{label}: HTTP {status} — {raw}", "unknown")


async def _request(
    hass: HomeAssistant,
    provider: str,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json: Any = None,
    timeout: int = 60,
) -> Any:
    session = async_get_clientsession(hass)
    try:
        async with session.request(
            method, url, headers=headers, json=json, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            try:
                body = await resp.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError):
                body = await resp.text()
            if resp.status >= 400:
                raise _friendly(provider, resp.status, body)
            return body
    except ProviderError:
        raise
    except TimeoutError as err:
        raise ProviderError(f"{PROVIDER_LABELS.get(provider, provider)}: request timed out", "cannot_connect") from err
    except aiohttp.ClientError as err:
        raise ProviderError(
            f"{PROVIDER_LABELS.get(provider, provider)}: cannot connect ({err})", "cannot_connect"
        ) from err


def _b64(img: bytes) -> str:
    return base64.b64encode(img).decode()


def _base(url: str | None, default: str) -> str:
    return (url or default).rstrip("/")


# ---------------------------------------------------------------- list models
async def async_list_models(hass: HomeAssistant, provider: str, api_key: str | None, base_url: str | None) -> list[str]:
    """Validate credentials and return the models available to this account."""
    if provider == PROVIDER_GEMINI:
        body = await _request(hass, provider, "GET", f"{GEMINI_URL}/models?key={api_key}&pageSize=200")
        models = [
            m["name"].removeprefix("models/")
            for m in body.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
            and "gemini" in m.get("name", "")
            and not any(x in m["name"] for x in ("embedding", "tts", "image-generation", "live"))
        ]
    elif provider == PROVIDER_OPENAI:
        body = await _request(
            hass, provider, "GET", f"{OPENAI_URL}/models", headers={"Authorization": f"Bearer {api_key}"}
        )
        skip = ("audio", "realtime", "tts", "transcribe", "embedding", "image", "search", "moderation", "dall-e", "whisper", "davinci", "babbage", "instruct")
        models = [
            m["id"] for m in body.get("data", [])
            if (m["id"].startswith(("gpt-", "o", "chatgpt-"))) and not any(s in m["id"] for s in skip)
        ]
    elif provider == PROVIDER_ANTHROPIC:
        body = await _request(
            hass, provider, "GET", f"{ANTHROPIC_URL}/models?limit=100",
            headers={"x-api-key": api_key or "", "anthropic-version": ANTHROPIC_VERSION},
        )
        models = [m["id"] for m in body.get("data", [])]
    elif provider == PROVIDER_OLLAMA:
        body = await _request(hass, provider, "GET", f"{_base(base_url, 'http://localhost:11434')}/api/tags", timeout=15)
        models = [m["name"] for m in body.get("models", [])]
    elif provider == PROVIDER_COMPATIBLE:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        body = await _request(hass, provider, "GET", f"{_base(base_url, OPENAI_URL)}/models", headers=headers, timeout=15)
        models = [m["id"] for m in body.get("data", [])] if isinstance(body, dict) else []
    else:
        return []
    return sorted(set(models))


# -------------------------------------------------------------------- analyze
async def async_analyze(
    hass: HomeAssistant,
    provider: str,
    *,
    api_key: str | None,
    base_url: str | None,
    model: str,
    prompt: str,
    images: list[bytes],
) -> str:
    """Send prompt + images to the provider and return the text reply."""
    if provider == PROVIDER_GEMINI:
        parts: list[dict[str, Any]] = [{"text": prompt}]
        parts += [{"inline_data": {"mime_type": "image/jpeg", "data": _b64(i)}} for i in images]
        body = await _request(
            hass, provider, "POST", f"{GEMINI_URL}/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key or ""},
            json={"contents": [{"role": "user", "parts": parts}], "generationConfig": {"maxOutputTokens": 1024}},
        )
        cands = body.get("candidates") or []
        if not cands:
            reason = (body.get("promptFeedback") or {}).get("blockReason", "empty response")
            raise ProviderError(f"Gemini returned no answer ({reason})")
        return "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))

    if provider in (PROVIDER_OPENAI, PROVIDER_COMPATIBLE):
        base = OPENAI_URL if provider == PROVIDER_OPENAI else _base(base_url, OPENAI_URL)
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content += [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(i)}", "detail": "low"}}
            for i in images
        ]
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        payload: dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": content}]}
        if provider == PROVIDER_OPENAI:
            payload["max_completion_tokens"] = 1024
        else:
            payload["max_tokens"] = MAX_TOKENS
        body = await _request(hass, provider, "POST", f"{base}/chat/completions", headers=headers, json=payload, timeout=90)
        return body["choices"][0]["message"].get("content") or ""

    if provider == PROVIDER_ANTHROPIC:
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(i)}}
            for i in images
        ]
        content.append({"type": "text", "text": prompt})
        body = await _request(
            hass, provider, "POST", f"{ANTHROPIC_URL}/messages",
            headers={"x-api-key": api_key or "", "anthropic-version": ANTHROPIC_VERSION},
            json={"model": model, "max_tokens": MAX_TOKENS, "messages": [{"role": "user", "content": content}]},
        )
        return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")

    if provider == PROVIDER_OLLAMA:
        body = await _request(
            hass, provider, "POST", f"{_base(base_url, 'http://localhost:11434')}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [{"role": "user", "content": prompt, "images": [_b64(i) for i in images]}],
            },
            timeout=240,
        )
        return (body.get("message") or {}).get("content", "")

    raise ProviderError(f"Unknown provider {provider}")


PROVIDER_LABELS = {
    PROVIDER_GEMINI: "Google Gemini",
    PROVIDER_OPENAI: "OpenAI",
    PROVIDER_ANTHROPIC: "Anthropic Claude",
    PROVIDER_OLLAMA: "Ollama",
    PROVIDER_COMPATIBLE: "OpenAI-compatible",
}
