from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from minicoder.agent import Agent
from minicoder.model_client import ModelResponse, ToolCall
from minicoder.tools import ToolRegistry


def tool_response(call_id: str, name: str, arguments: dict) -> ModelResponse:
    return ModelResponse(
        tool_calls=[ToolCall(call_id, name, arguments)],
        raw_tool_calls=[
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments),
                },
            }
        ],
    )


class ScriptedClient:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelResponse:
        return self.responses.pop(0)


class RepairLoopTests(unittest.TestCase):
    def test_failed_verification_then_edit_is_a_repair_round(self) -> None:
        events: list[tuple[str, dict]] = []
        with tempfile.TemporaryDirectory() as directory:
            client = ScriptedClient(
                [
                    tool_response(
                        "write",
                        "write_file",
                        {"path": "answer.py", "content": "raise RuntimeError('bad')\n"},
                    ),
                    tool_response(
                        "fail", "run_command", {"command": "python answer.py"}
                    ),
                    tool_response(
                        "repair",
                        "replace_in_file",
                        {
                            "path": "answer.py",
                            "old_text": "raise RuntimeError('bad')",
                            "new_text": "print(42)",
                        },
                    ),
                    tool_response(
                        "pass", "run_command", {"command": "python answer.py"}
                    ),
                    ModelResponse(content="Fixed the program and verified it."),
                ]
            )
            result = Agent(
                client,
                ToolRegistry(Path(directory)),
                max_steps=7,
                event_handler=lambda event, data: events.append((event, data)),
            ).run("Create a working answer.py")

        report = result.verification.to_dict()
        self.assertEqual(result.status, "verified")
        self.assertGreaterEqual(result.duration_seconds, 0)
        self.assertEqual(report["failed_verifications"], 1)
        self.assertEqual(report["successful_verifications"], 1)
        self.assertEqual(len(report["repair_rounds"]), 1)
        self.assertEqual(report["repair_rounds"][0]["changed_file"], "answer.py")
        self.assertEqual(
            [name for name, _ in events].count("verification_result"), 2
        )
        self.assertEqual([name for name, _ in events].count("repair_started"), 1)

    def test_completion_rejection_is_counted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = ScriptedClient(
                [
                    tool_response(
                        "write",
                        "write_file",
                        {"path": "answer.py", "content": "print(42)\n"},
                    ),
                    ModelResponse(content="Done without verification."),
                    tool_response(
                        "pass", "run_command", {"command": "python answer.py"}
                    ),
                    ModelResponse(content="Now verified."),
                ]
            )
            result = Agent(client, ToolRegistry(Path(directory)), max_steps=6).run(
                "Create and verify answer.py"
            )

        self.assertEqual(result.verification.completion_rejections, 1)


if __name__ == "__main__":
    unittest.main()
