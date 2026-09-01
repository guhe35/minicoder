"""Render sprint execution plans for a release meeting."""

from __future__ import annotations

from typing import Any


def render_markdown_plan(waves: list[list[dict[str, Any]]]) -> str:
    """Render a deterministic Markdown summary for an execution plan."""
    lines = ["# Sprint Execution Plan", ""]

    if not waves:
        lines.append("No pending tasks.")
        return "\n".join(lines)

    pending_count = 0
    for wave_number, wave in enumerate(waves, start=1):
        lines.append(f"## Wave {wave_number}")
        for task in wave:
            pending_count += 1
            priority = str(task["priority"]).upper()
            lines.append(f"- [{priority}] {task['id']} — {task['title']}")
        lines.append("")

    lines.append(f"Summary: {pending_count} pending task(s) across {len(waves)} wave(s).")
    return "\n".join(lines)
