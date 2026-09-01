"""Render sprint execution plans for a release meeting."""

from __future__ import annotations

from typing import Any


def render_markdown_plan(waves: list[list[dict[str, Any]]]) -> str:
    """Render a Markdown summary for an execution plan.

    The starter only renders the title; TASK.md describes the required output.
    """
    return "# Sprint Execution Plan\n"
