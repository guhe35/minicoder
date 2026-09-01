"""Build deterministic execution waves from sprint tasks."""

from __future__ import annotations

from typing import Any


class PlanningError(ValueError):
    """Raised when task data cannot form a valid execution plan."""


def build_execution_plan(tasks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Return execution waves for the given sprint tasks.

    This starter implementation is intentionally incomplete. Use TASK.md and
    the test suite as the specification.
    """
    if not tasks:
        return []

    return [list(tasks)]
