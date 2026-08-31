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
                        tool_calls=[ToolCall("call_write", "write_file", {"path": "answer.py", "content": "print(42)\n"})],
                        raw_tool_calls=[first_raw],
                    ),
                    ModelResponse(
                        tool_calls=[ToolCall("call_run", "run_command", {"command": "python answer.py"})],
                        raw_tool_calls=[second_raw],
                    ),
                    ModelResponse(content="Created answer.py and verified that it prints 42."),
                ]
            )
            agent = Agent(client, ToolRegistry(Path(directory)), max_steps=5)
            result = agent.run("Create a program that prints 42 and test it.")

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.steps, 3)
            self.assertEqual((Path(directory) / "answer.py").read_text(), "print(42)\n")
            tool_messages = [message for message in result.messages if message["role"] == "tool"]
            self.assertEqual(len(tool_messages), 2)
            self.assertIn('"exit_code": 0', tool_messages[1]["content"])

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

