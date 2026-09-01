from __future__ import annotations

import unittest

from minicoder.evaluation import REPORT_SCHEMA, summarize_run_records


class EvaluationTests(unittest.TestCase):
    def test_summarizes_multiple_run_reports(self) -> None:
        records = [
            {
                "schema": REPORT_SCHEMA,
                "outcome": {
                    "status": "verified",
                    "steps": 8,
                    "duration_seconds": 12.5,
                },
                "verification": {
                    "failed_verifications": 1,
                    "repair_rounds": [{"number": 1}],
                    "completion_rejections": 0,
                },
            },
            {
                "schema": REPORT_SCHEMA,
                "outcome": {
                    "status": "step_limit",
                    "steps": 15,
                    "duration_seconds": 20,
                },
                "verification": {
                    "failed_verifications": 2,
                    "repair_rounds": [],
                    "completion_rejections": 1,
                },
            },
        ]

        summary = summarize_run_records(records)

        self.assertEqual(summary["runs"], 2)
        self.assertEqual(summary["successful_runs"], 1)
        self.assertEqual(summary["success_rate"], 0.5)
        self.assertEqual(summary["average_steps"], 11.5)
        self.assertEqual(summary["failed_verifications"], 3)
        self.assertEqual(summary["repair_rounds"], 1)
        self.assertEqual(summary["completion_rejections"], 1)

    def test_rejects_empty_or_unknown_reports(self) -> None:
        with self.assertRaises(ValueError):
            summarize_run_records([])
        with self.assertRaises(ValueError):
            summarize_run_records([{"schema": "unknown"}])


if __name__ == "__main__":
    unittest.main()
