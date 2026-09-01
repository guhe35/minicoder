"""Command-line interface for MiniCoder."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .agent import Agent
from .config import Config
from .evaluation import build_run_record
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
    elif event == "verification_result":
        marker = "pass" if data["exit_code"] == 0 else "fail"
        print(f"  [{marker}] verification: {data['command']}")
    elif event == "repair_started":
        print(
            f"  [repair {data['number']}] {data['failed_command']} -> "
            f"editing {data['changed_file']}"
        )
    elif event == "completion_rejected":
        print(f"  !! completion rejected: {data['reason']}")


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
    parser.add_argument(
        "--report", type=Path, help="Write a structured run-report JSON file"
    )
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
        if args.report:
            record = build_run_record(task, str(args.workspace), result)
            args.report.write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(
        f"\n[{result.status}] after {result.steps} step(s), "
        f"{result.duration_seconds:.1f}s\n{result.answer}"
    )
    print(f"\n{result.verification.format_text()}")
    if args.report:
        print(f"Run report: {args.report}")
    return 0 if result.status in {"completed", "verified"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
