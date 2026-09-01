"""Run a visible planning example after the implementation is complete."""

from sprint_planner import build_execution_plan, render_markdown_plan


TASKS = [
    {
        "id": "schema",
        "title": "Finalize database schema",
        "priority": "high",
        "depends_on": [],
        "done": False,
    },
    {
        "id": "api",
        "title": "Implement task API",
        "priority": "high",
        "depends_on": ["schema"],
        "done": False,
    },
    {
        "id": "docs",
        "title": "Write migration guide",
        "priority": "low",
        "depends_on": [],
        "done": False,
    },
    {
        "id": "release",
        "title": "Publish release candidate",
        "priority": "medium",
        "depends_on": ["api", "docs"],
        "done": False,
    },
]


if __name__ == "__main__":
    print(render_markdown_plan(build_execution_plan(TASKS)))
