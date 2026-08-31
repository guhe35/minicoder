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
    request_timeout: int = 90
    max_retries: int = 2

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Config":
        load_dotenv(env_file or Path(".env"))
        return cls(
            api_url=os.getenv("MODEL_API_URL", ""),
            api_key=os.getenv("MODEL_API_KEY", ""),
            model=os.getenv("MODEL_NAME", ""),
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

