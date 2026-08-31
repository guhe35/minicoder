"""Command-line interface for MiniCoder."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .agent import Agent
from .config import Config
from .model_client import OpenAICompatibleClient
from .tools import ToolRegistry


def print_event(event: str, data: dict[str, Any]) -> None:
    if event == "model_request":
        print(f"\n[step {data['step']}] asking model...")
    elif event == "tool_start":
        args = json.dumps(data["arguments"], ensure_ascii=False)
        print(f"  -> {data['tool']} {args}")
    elif event == "tool_end":
        result = data["result"]
        marker = "ok" if result.get("ok") else "error"
        preview = json.dumps(result, ensure_ascii=False)
        if len(preview) > 700:
            preview = preview[:700] + "..."
        print(f"  <- {marker}: {preview}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minicoder", description="A small coding agent without agent frameworks"
    )
    parser.add_argument("task", nargs="?", help="Programming task for the agent")
    parser.add_argument(
        "--workspace", default=".", help="Directory the agent is allowed to modify"
    )
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--env-file", default=".env")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    task = args.task or input("Task: ").strip()
    try:
        config = Config.from_env(Path(args.env_file))
        client = OpenAICompatibleClient(config)
        tools = ToolRegistry(Path(args.workspace))
        agent = Agent(
            client=client,
            tools=tools,
            max_steps=args.max_steps,
            event_handler=print_event,
        )
        result = agent.run(task)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"\n[{result.status}] after {result.steps} step(s)\n{result.answer}")
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

