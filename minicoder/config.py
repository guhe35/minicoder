"""Configuration loading for MiniCoder."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PLACEHOLDER_MARKERS = ("YOUR_", "example")


def load_dotenv(path: Path) -> None:
    """Load a minimal KEY=VALUE file without overriding existing variables."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Config:
    api_url: str
    api_key: str
    model: str
    thinking_mode: str | None = None
    reasoning_effort: str | None = None
    request_timeout: int = 90
    max_retries: int = 2

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Config":
        load_dotenv(env_file or Path(".env"))
        return cls(
            api_url=os.getenv("MODEL_API_URL", ""),
            api_key=os.getenv("MODEL_API_KEY", ""),
            model=os.getenv("MODEL_NAME", ""),
            thinking_mode=os.getenv("MODEL_THINKING") or None,
            reasoning_effort=os.getenv("MODEL_REASONING_EFFORT") or None,
            request_timeout=int(os.getenv("MODEL_TIMEOUT_SECONDS", "90")),
            max_retries=int(os.getenv("MODEL_MAX_RETRIES", "2")),
        )

    def validate(self) -> None:
        values = {
            "MODEL_API_URL": self.api_url,
            "MODEL_API_KEY": self.api_key,
            "MODEL_NAME": self.model,
        }
        missing = [
            name
            for name, value in values.items()
            if not value or any(marker.lower() in value.lower() for marker in PLACEHOLDER_MARKERS)
        ]
        if missing:
            names = ", ".join(missing)
            raise ValueError(
                f"Model configuration is incomplete: {names}. "
                "Copy .env.example to .env and replace its placeholders."
            )
        if self.thinking_mode not in {None, "enabled", "disabled"}:
            raise ValueError("MODEL_THINKING must be 'enabled' or 'disabled'")
        if self.reasoning_effort not in {
            None,
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        }:
            raise ValueError(
                "MODEL_REASONING_EFFORT must be low, medium, high, xhigh, or max"
            )
        if self.request_timeout < 1:
            raise ValueError("MODEL_TIMEOUT_SECONDS must be positive")
        if self.max_retries < 0:
            raise ValueError("MODEL_MAX_RETRIES must not be negative")
