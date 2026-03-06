# api_client.py
# Thin streaming HTTP client for Groq and OpenRouter.
#
# Both providers expose an OpenAI-compatible /chat/completions endpoint.
# Only `requests` is used (already a transitive dep of `transformers`).
#
# Live model lists are fetched via each provider's /models endpoint so the
# user always sees every model that is available on their account.

from __future__ import annotations

import json
from typing import Iterator

import requests

# ── Fallback model lists (shown before "Fetch Models" is clicked) ─────────────
PROVIDERS: dict[str, dict] = {
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "fallback_models": [
            "openai/gpt-oss-120b",
            "qwen-2.5-coder-32b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "deepseek-r1-distill-llama-70b",
            "gemma2-9b-it",
            "mixtral-8x7b-32768",
        ],
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "fallback_models": [
            "deepseek/deepseek-chat-v3-0324:free",
            "meta-llama/llama-4-maverick:free",
            "google/gemma-3-27b-it:free",
            "deepseek/deepseek-r1:free",
            "anthropic/claude-3.5-haiku",
            "openai/gpt-4o-mini",
        ],
    },
}


class ApiClient:
    """
    Streams chat completions from Groq or OpenRouter and can fetch the
    live list of models available on the account.

    Usage
    ─────
    client = ApiClient("Groq", api_key="gsk_...", model="qwen-2.5-coder-32b")

    # Stream tokens
    for chunk in client.generate_stream(messages):
        print(chunk, end="", flush=True)

    # Fetch available models
    models = client.get_models()
    """

    def __init__(
        self,
        provider: str,
        api_key:  str,
        model:    str | None = None,
    ) -> None:
        if provider not in PROVIDERS:
            raise ValueError(
                f"Unknown provider {provider!r}. "
                f"Choose from: {list(PROVIDERS)}"
            )
        self.provider = provider
        self.api_key  = api_key.strip()
        cfg           = PROVIDERS[provider]
        self.base_url = cfg["base_url"]
        self.model    = model or cfg["fallback_models"][0]

    # ── Model discovery ───────────────────────────────────────────────────────

    def get_models(self) -> list[str]:
        """
        Fetch the full list of model IDs available on the account.

        Returns a sorted list of model ID strings.
        Raises `requests.HTTPError` on non-2xx responses (e.g. invalid key).
        """
        url     = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.provider == "OpenRouter":
            headers["HTTP-Referer"] = "https://github.com/ai-coder-ide"
            headers["X-Title"]      = "AI Coder IDE"

        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Both providers return {"data": [{"id": "...", ...}, ...]}
        ids = [item["id"] for item in data.get("data", []) if "id" in item]

        # For OpenRouter put :free models first, then sort alphabetically
        if self.provider == "OpenRouter":
            free   = sorted(m for m in ids if ":free" in m)
            paid   = sorted(m for m in ids if ":free" not in m)
            return free + paid

        return sorted(ids)

    # ── Streaming generation ──────────────────────────────────────────────────

    def generate_stream(self, messages: list[dict]) -> Iterator[str]:
        """
        Yield text chunks as they arrive via Server-Sent Events.
        Raises `requests.HTTPError` on non-2xx responses.
        """
        url     = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }
        if self.provider == "OpenRouter":
            headers["HTTP-Referer"] = "https://github.com/ai-coder-ide"
            headers["X-Title"]      = "AI Coder IDE"

        payload = {
            "model":    self.model,
            "messages": messages,
            "stream":   True,
        }

        with requests.post(
            url,
            headers=headers,
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace")
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    obj   = json.loads(data)
                    delta = obj["choices"][0]["delta"]
                    text  = delta.get("content") or ""
                    if text:
                        yield text
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
