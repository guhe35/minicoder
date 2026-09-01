from __future__ import annotations

import unittest

from sprint_planner.planner import PlanningError, build_execution_plan


def task(
    task_id: str,
    *,
    priority: str = "medium",
    depends_on: list[str] | None = None,
    done: bool = False,
) -> dict:
    return {
        "id": task_id,
        "title": f"Task {task_id}",
        "priority": priority,
        "depends_on": list(depends_on or []),
        "done": done,
    }


class ExecutionPlanTests(unittest.TestCase):
    def test_builds_dependency_waves_and_sorts_each_wave(self) -> None:
        tasks = [
            task("release", priority="medium", depends_on=["api", "docs"]),
            task("docs", priority="low"),
            task("api", priority="high", depends_on=["schema"]),
            task("schema", priority="high"),
            task("lint", priority="medium"),
        ]

        waves = build_execution_plan(tasks)

        self.assertEqual(
            [[item["id"] for item in wave] for wave in waves],
            [["schema", "lint", "docs"], ["api"], ["release"]],
        )

    def test_completed_tasks_are_omitted_and_satisfy_dependencies(self) -> None:
        tasks = [task("foundation", done=True), task("api", depends_on=["foundation"])]

        waves = build_execution_plan(tasks)

        self.assertEqual([[item["id"] for item in wave] for wave in waves], [["api"]])

    def test_result_is_deeply_isolated_from_input(self) -> None:
        tasks = [task("api")]

        waves = build_execution_plan(tasks)
        waves[0][0]["title"] = "Changed"
        waves[0][0]["depends_on"].append("other")

        self.assertEqual(tasks[0]["title"], "Task api")
        self.assertEqual(tasks[0]["depends_on"], [])

    def test_rejects_duplicate_ids(self) -> None:
        with self.assertRaises(PlanningError):
            build_execution_plan([task("api"), task("api")])

    def test_rejects_missing_dependency(self) -> None:
        with self.assertRaises(PlanningError):
            build_execution_plan([task("api", depends_on=["schema"])])

    def test_rejects_cycle(self) -> None:
        with self.assertRaises(PlanningError):
            build_execution_plan(
                [task("api", depends_on=["ui"]), task("ui", depends_on=["api"])]
            )

    def test_rejects_self_dependency(self) -> None:
        with self.assertRaises(PlanningError):
            build_execution_plan([task("api", depends_on=["api"])])

    def test_rejects_invalid_priority(self) -> None:
        with self.assertRaises(PlanningError):
            build_execution_plan([task("api", priority="urgent")])

    def test_empty_input_has_no_waves(self) -> None:
        self.assertEqual(build_execution_plan([]), [])

    def test_all_completed_tasks_are_omitted(self) -> None:
        tasks = [
            task("foundation", done=True),
            task("api", depends_on=["foundation"], done=True),
        ]

        self.assertEqual(build_execution_plan(tasks), [])


if __name__ == "__main__":
    unittest.main()
