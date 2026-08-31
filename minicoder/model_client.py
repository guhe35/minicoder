"""A minimal OpenAI-compatible chat-completions client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from .config import Config


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_tool_calls: list[dict[str, Any]] = field(default_factory=list)


class ModelClient(Protocol):
    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelResponse: ...


class OpenAICompatibleClient:
    """Call a provider exposing an OpenAI-compatible chat completions endpoint."""

    def __init__(self, config: Config):
        config.validate()
        self.config = config

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelResponse:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.1,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.config.api_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                with urllib.request.urlopen(
                    request, timeout=self.config.request_timeout
                ) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return self._parse_response(data)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Model request failed after retries: {last_error}") from last_error

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> ModelResponse:
        message = data["choices"][0]["message"]
        raw_calls = message.get("tool_calls") or []
        calls: list[ToolCall] = []
        for raw_call in raw_calls:
            function = raw_call.get("function", {})
            raw_arguments = function.get("arguments", "{}")
            try:
                arguments = (
                    raw_arguments
                    if isinstance(raw_arguments, dict)
                    else json.loads(raw_arguments or "{}")
                )
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Model returned invalid tool arguments for {function.get('name')}: {exc}"
                ) from exc
            calls.append(
                ToolCall(
                    id=raw_call.get("id", f"call_{len(calls) + 1}"),
                    name=function.get("name", ""),
                    arguments=arguments,
                )
            )
        return ModelResponse(
            content=message.get("content") or "",
            tool_calls=calls,
            raw_tool_calls=raw_calls,
        )

