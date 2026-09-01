from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from minicoder.agent import Agent
from minicoder.model_client import ModelResponse, ToolCall
from minicoder.tools import ToolRegistry


def raw_call(call_id: str, name: str, arguments: str) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


class ScriptedClient:
    def __init__(self, responses: list[ModelResponse]):
        self.responses = responses
        self.requests: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelResponse:
        self.requests.append(list(messages))
        return self.responses.pop(0)


class AgentLoopTests(unittest.TestCase):
    def test_full_model_tool_model_loop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first_raw = raw_call("call_write", "write_file", '{"path":"answer.py","content":"print(42)\\n"}')
            second_raw = raw_call("call_run", "run_command", '{"command":"python answer.py"}')
            client = ScriptedClient(
                [
                    ModelResponse(
                        reasoning_content="I will create the requested file.",
                        tool_calls=[ToolCall("call_write", "write_file", {"path": "answer.py", "content": "print(42)\n"})],
                        raw_tool_calls=[first_raw],
                    ),
                    ModelResponse(
                        reasoning_content="The file is ready; now I should run it.",
                        tool_calls=[ToolCall("call_run", "run_command", {"command": "python answer.py"})],
                        raw_tool_calls=[second_raw],
                    ),
                    ModelResponse(content="Created answer.py and verified that it prints 42."),
                ]
            )
            agent = Agent(client, ToolRegistry(Path(directory)), max_steps=5)
            result = agent.run("Create a program that prints 42 and test it.")

            self.assertEqual(result.status, "verified")
            self.assertEqual(result.steps, 3)
            self.assertEqual(result.verification.status, "verified")
            self.assertEqual(result.verification.changed_files, ["answer.py"])
            self.assertEqual(result.verification.verification_runs[-1].exit_code, 0)
            self.assertEqual((Path(directory) / "answer.py").read_text(), "print(42)\n")
            tool_messages = [message for message in result.messages if message["role"] == "tool"]
            self.assertEqual(len(tool_messages), 2)
            self.assertIn('"exit_code": 0', tool_messages[1]["content"])
            replayed_assistant = client.requests[1][-2]
            self.assertEqual(replayed_assistant["role"], "assistant")
            self.assertEqual(
                replayed_assistant["reasoning_content"],
                "I will create the requested file.",
            )

    def test_completion_gate_requires_post_change_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_raw = raw_call(
                "call_write",
                "write_file",
                '{"path":"answer.py","content":"print(42)\\n"}',
            )
            run_raw = raw_call(
                "call_run", "run_command", '{"command":"python answer.py"}'
            )
            client = ScriptedClient(
                [
                    ModelResponse(
                        tool_calls=[
                            ToolCall(
                                "call_write",
                                "write_file",
                                {"path": "answer.py", "content": "print(42)\n"},
                            )
                        ],
                        raw_tool_calls=[write_raw],
                    ),
                    ModelResponse(content="Done without testing."),
                    ModelResponse(
                        tool_calls=[
                            ToolCall(
                                "call_run",
                                "run_command",
                                {"command": "python answer.py"},
                            )
                        ],
                        raw_tool_calls=[run_raw],
                    ),
                    ModelResponse(content="Created and verified answer.py."),
                ]
            )

            result = Agent(client, ToolRegistry(Path(directory)), max_steps=6).run(
                "Create and verify answer.py"
            )

            self.assertEqual(result.status, "verified")
            self.assertEqual(result.steps, 4)
            gate_feedback = client.requests[2][-1]
            self.assertEqual(gate_feedback["role"], "user")
            self.assertIn("Completion rejected", gate_feedback["content"])

    def test_failed_verification_is_rejected_until_a_check_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_raw = raw_call(
                "call_write",
                "write_file",
                '{"path":"answer.py","content":"print(42)\\n"}',
            )
            failed_raw = raw_call(
                "call_fail", "run_command", '{"command":"python missing.py"}'
            )
            passed_raw = raw_call(
                "call_pass", "run_command", '{"command":"python answer.py"}'
            )
            client = ScriptedClient(
                [
                    ModelResponse(
                        tool_calls=[
                            ToolCall(
                                "call_write",
                                "write_file",
                                {"path": "answer.py", "content": "print(42)\n"},
                            )
                        ],
                        raw_tool_calls=[write_raw],
                    ),
                    ModelResponse(
                        tool_calls=[
                            ToolCall(
                                "call_fail",
                                "run_command",
                                {"command": "python missing.py"},
                            )
                        ],
                        raw_tool_calls=[failed_raw],
                    ),
                    ModelResponse(content="Finished despite the failure."),
                    ModelResponse(
                        tool_calls=[
                            ToolCall(
                                "call_pass",
                                "run_command",
                                {"command": "python answer.py"},
                            )
                        ],
                        raw_tool_calls=[passed_raw],
                    ),
                    ModelResponse(content="The executable check now passes."),
                ]
            )

            result = Agent(client, ToolRegistry(Path(directory)), max_steps=7).run(
                "Create and verify answer.py"
            )

            self.assertEqual(result.status, "verified")
            self.assertEqual(len(result.verification.verification_runs), 2)
            self.assertNotEqual(result.verification.verification_runs[0].exit_code, 0)
            self.assertEqual(result.verification.verification_runs[1].exit_code, 0)

    def test_read_only_task_does_not_require_verification(self) -> None:
        client = ScriptedClient([ModelResponse(content="The project is healthy.")])
        with tempfile.TemporaryDirectory() as directory:
            result = Agent(client, ToolRegistry(Path(directory))).run("Explain the project")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.verification.status, "completed")
        self.assertEqual(result.verification.changed_files, [])

    def test_step_limit_stops_runaway_agent(self) -> None:
        call = raw_call("call_1", "list_files", "{}")
        response = ModelResponse(
            tool_calls=[ToolCall("call_1", "list_files", {})], raw_tool_calls=[call]
        )
        client = ScriptedClient([response, response])
        with tempfile.TemporaryDirectory() as directory:
            result = Agent(client, ToolRegistry(Path(directory)), max_steps=2).run("Keep looking")
        self.assertEqual(result.status, "step_limit")
        self.assertEqual(result.steps, 2)


if __name__ == "__main__":
    unittest.main()
