"""Build deterministic execution waves from sprint tasks."""

from __future__ import annotations

import copy
from typing import Any


class PlanningError(ValueError):
    """Raised when task data cannot form a valid execution plan."""


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_ALLOWED_PRIORITIES = frozenset(_PRIORITY_ORDER)


def _validate_task(task: dict[str, Any]) -> None:
    if not isinstance(task, dict):
        raise PlanningError("Each task must be a dictionary.")

    task_id = task.get("id")
    title = task.get("title")
    priority = task.get("priority")
    depends_on = task.get("depends_on")
    done = task.get("done")

    if not isinstance(task_id, str) or not task_id:
        raise PlanningError("Task 'id' must be a non-empty string.")
    if not isinstance(title, str) or not title:
        raise PlanningError("Task 'title' must be a non-empty string.")
    if priority not in _ALLOWED_PRIORITIES:
        raise PlanningError(
            f"Task '{task_id}' has invalid priority {priority!r}; "
            "expected high, medium, or low."
        )
    if not isinstance(depends_on, list) or any(
        not isinstance(dep_id, str) or not dep_id for dep_id in depends_on
    ):
        raise PlanningError(
            f"Task '{task_id}' has invalid depends_on; expected a list of non-empty strings."
        )
    if not isinstance(done, bool):
        raise PlanningError(f"Task '{task_id}' has invalid done; expected a bool.")


def build_execution_plan(tasks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Return dependency-safe execution waves.

    Completed tasks are omitted from the result, but their IDs are treated as
    already-satisfied dependencies.  Validation errors are raised uniformly as
    :class:`PlanningError`.
    """
    if not isinstance(tasks, list):
        raise PlanningError("Tasks must be a list.")

    working_tasks = copy.deepcopy(tasks)

    for task in working_tasks:
        _validate_task(task)

    ids = [task["id"] for task in working_tasks]
    if len(ids) != len(set(ids)):
        raise PlanningError("Duplicate task IDs are not allowed.")

    id_set = set(ids)
    for task in working_tasks:
        task_id = task["id"]
        for dep_id in task["depends_on"]:
            if dep_id not in id_set:
                raise PlanningError(
                    f"Task '{task_id}' depends on missing task '{dep_id}'."
                )
            if dep_id == task_id:
                raise PlanningError(f"Task '{task_id}' cannot depend on itself.")

    pending_tasks = [task for task in working_tasks if not task["done"]]
    if not pending_tasks:
        return []

    satisfied = {task["id"] for task in working_tasks if task["done"]}
    waves: list[list[dict[str, Any]]] = []
    remaining = pending_tasks

    while remaining:
        ready = [
            task
            for task in remaining
            if all(dep_id in satisfied for dep_id in task["depends_on"])
        ]

        if not ready:
            raise PlanningError("Circular dependency detected among pending tasks.")

        ready.sort(key=lambda task: (_PRIORITY_ORDER[task["priority"]], task["id"]))
        waves.append(ready)

        for task in ready:
            satisfied.add(task["id"])

        ready_ids = {task["id"] for task in ready}
        remaining = [task for task in remaining if task["id"] not in ready_ids]

    return waves
