from __future__ import annotations

import unittest

from sprint_planner.report import render_markdown_plan


class MarkdownReportTests(unittest.TestCase):
    def test_renders_waves_tasks_and_summary(self) -> None:
        waves = [
            [
                {"id": "schema", "title": "Finalize schema", "priority": "high"},
                {"id": "docs", "title": "Write guide", "priority": "low"},
            ],
            [{"id": "api", "title": "Implement API", "priority": "medium"}],
        ]

        report = render_markdown_plan(waves)

        self.assertEqual(
            report,
            "# Sprint Execution Plan\n\n"
            "## Wave 1\n"
            "- [HIGH] schema — Finalize schema\n"
            "- [LOW] docs — Write guide\n\n"
            "## Wave 2\n"
            "- [MEDIUM] api — Implement API\n\n"
            "Summary: 3 pending task(s) across 2 wave(s).",
        )

    def test_renders_empty_plan(self) -> None:
        self.assertEqual(
            render_markdown_plan([]),
            "# Sprint Execution Plan\n\nNo pending tasks.",
        )


if __name__ == "__main__":
    unittest.main()
