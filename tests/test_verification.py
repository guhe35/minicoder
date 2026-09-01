from __future__ import annotations

import unittest

from minicoder.verification import ExecutionState, classify_verification_command


class VerificationTests(unittest.TestCase):
    def test_classifies_supported_evidence_commands(self) -> None:
        cases = {
            "pytest -q": "test",
            "python -m unittest discover -s tests": "test",
            "npm run test:unit": "test",
            "mvn verify": "test",
            "cargo check": "build",
            "python demo.py": "execution",
            "git status": None,
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(classify_verification_command(command), expected)

    def test_test_before_latest_change_is_stale(self) -> None:
        state = ExecutionState()
        state.record_tool_call(
            "write_file", {"path": "a.py"}, {"ok": True, "path": "a.py"}
        )
        state.record_tool_call(
            "run_command",
            {"command": "python a.py"},
            {"ok": True, "command": "python a.py", "exit_code": 0},
        )
        state.record_tool_call(
            "replace_in_file", {"path": "a.py"}, {"ok": True, "path": "a.py"}
        )

        check = state.check_completion()

        self.assertFalse(check.allowed)
        self.assertIn("after the latest change", check.reason)

    def test_latest_failed_verification_blocks_completion(self) -> None:
        state = ExecutionState()
        state.record_tool_call(
            "write_file", {"path": "a.py"}, {"ok": True, "path": "a.py"}
        )
        state.record_tool_call(
            "run_command",
            {"command": "pytest"},
            {"ok": True, "command": "pytest", "exit_code": 1},
        )

        check = state.check_completion()

        self.assertFalse(check.allowed)
        self.assertIn("exit code 1", check.reason)


if __name__ == "__main__":
    unittest.main()
