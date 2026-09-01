"""Structured run reports and lightweight aggregate evaluation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .agent import AgentResult


REPORT_SCHEMA = "minicoder.run-report.v1"


def build_run_record(
    task: str,
    workspace: str,
    result: AgentResult,
) -> dict[str, Any]:
    """Create a portable record suitable for download and later comparison."""
    return {
        "schema": REPORT_SCHEMA,
        "run_id": uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "workspace": workspace,
        "outcome": {
            "status": result.status,
            "answer": result.answer,
            "steps": result.steps,
            "duration_seconds": result.duration_seconds,
        },
        "verification": result.verification.to_dict(),
    }


def summarize_run_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate downloaded reports into reproducible evaluation metrics."""
    items = list(records)
    if not items:
        raise ValueError("At least one run report is required")
    for item in items:
        if item.get("schema") != REPORT_SCHEMA:
            raise ValueError("Unsupported or missing MiniCoder report schema")

    outcomes = [item["outcome"] for item in items]
    verification = [item["verification"] for item in items]
    successes = sum(
        outcome.get("status") in {"verified", "completed"} for outcome in outcomes
    )
    return {
        "schema": "minicoder.evaluation-summary.v1",
        "runs": len(items),
        "successful_runs": successes,
        "success_rate": round(successes / len(items), 4),
        "verified_runs": sum(
            outcome.get("status") == "verified" for outcome in outcomes
        ),
        "average_steps": round(
            sum(float(outcome.get("steps", 0)) for outcome in outcomes) / len(items),
            2,
        ),
        "average_duration_seconds": round(
            sum(float(outcome.get("duration_seconds", 0)) for outcome in outcomes)
            / len(items),
            3,
        ),
        "failed_verifications": sum(
            int(report.get("failed_verifications", 0)) for report in verification
        ),
        "repair_rounds": sum(
            len(report.get("repair_rounds", [])) for report in verification
        ),
        "completion_rejections": sum(
            int(report.get("completion_rejections", 0)) for report in verification
        ),
    }


def _load_records(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.extend(payload if isinstance(payload, list) else [payload])
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minicoder-eval",
        description="Aggregate MiniCoder run-report JSON files",
    )
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, help="Optional summary JSON path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = summarize_run_records(_load_records(args.reports))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        return 2
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
