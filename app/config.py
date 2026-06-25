"""Configuration loaded strictly from environment variables.

Secrets must never be hard-coded. The application reads ``LLM_API_KEY``,
``LLM_BASE_URL``, ``LLM_MODEL`` and ``MAX_MESSAGE_BYTES`` from the process
environment at import time.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    max_message_bytes: int


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_settings() -> Settings:
    """Read settings from the environment. Raises if the API key is missing."""
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "LLM_API_KEY is not set. Set it in your environment or in a "
            "local .env file (which is gitignored)."
        )
    return Settings(
        llm_api_key=api_key,
        llm_base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        max_message_bytes=_int_env("MAX_MESSAGE_BYTES", 4096),
    )


SETTINGS = load_settings()
