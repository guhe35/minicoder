"""The model-tool-model control loop."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from .model_client import ModelClient
from .tools import ToolRegistry
from .verification import ExecutionState, VerificationReport


SYSTEM_PROMPT = """You are MiniCoder, a coding agent working in a local project workspace.
Use tools to inspect the project before editing. Make the smallest correct change, run relevant tests,
and recover from tool or test failures. Never invent tool results. Keep all work inside the workspace.
If a verification command fails, inspect its output, repair the code, and run verification again.
If you modify files, a recognized verification command must succeed after the latest modification;
otherwise the deterministic completion gate will reject your final answer and ask you to continue.
When the task is complete, respond with a concise summary of changes and tests. If blocked, explain why.
"""


@dataclass
class AgentResult:
    status: str
    answer: str
    steps: int
    messages: list[dict[str, Any]]
    verification: VerificationReport
    duration_seconds: float


class Agent:
    def __init__(
        self,
        client: ModelClient,
        tools: ToolRegistry,
        max_steps: int = 15,
        event_handler: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self.client = client
        self.tools = tools
        self.max_steps = max_steps
        self.event_handler = event_handler or (lambda _event, _data: None)

    def run(self, task: str) -> AgentResult:
        if not task.strip():
            raise ValueError("Task must not be empty")
        started_at = time.perf_counter()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task.strip()},
        ]
        state = ExecutionState()

        def build_result(status: str, answer: str, steps: int) -> AgentResult:
            return AgentResult(
                status=status,
                answer=answer,
                steps=steps,
                messages=messages,
                verification=state.build_report(),
                duration_seconds=round(time.perf_counter() - started_at, 3),
            )

        for step in range(1, self.max_steps + 1):
            self.event_handler("model_request", {"step": step})
            state.record_model_call()
            response = self.client.complete(messages, self.tools.schemas)

            if not response.tool_calls:
                answer = (response.content or "").strip()
                if not answer:
                    answer = "The model returned neither a tool call nor a final answer."
                    status = "error"
                    messages.append({"role": "assistant", "content": answer})
                    self.event_handler("finished", {"step": step, "status": status})
                    return build_result(status, answer, step)

                final_message: dict[str, Any] = {"role": "assistant", "content": answer}
                if response.reasoning_content is not None:
                    final_message["reasoning_content"] = response.reasoning_content
                messages.append(final_message)

                completion = state.check_completion()
                if not completion.allowed:
                    state.record_completion_rejection()
                    feedback = (
                        "[Automated verification gate] Completion rejected: "
                        f"{completion.reason} Continue working, inspect failed output, "
                        "run an appropriate test, build, or executable check with "
                        "run_command, and only then finish."
                    )
                    messages.append({"role": "user", "content": feedback})
                    self.event_handler(
                        "completion_rejected",
                        {"step": step, "reason": completion.reason},
                    )
                    continue

                status = completion.status
                self.event_handler("finished", {"step": step, "status": status})
                return build_result(status, answer, step)

            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": response.content or None,
                "tool_calls": response.raw_tool_calls,
            }
            if response.reasoning_content is not None:
                assistant_message["reasoning_content"] = response.reasoning_content
            messages.append(assistant_message)

            for call in response.tool_calls:
                self.event_handler(
                    "tool_start",
                    {"step": step, "tool": call.name, "arguments": call.arguments},
                )
                result = self.tools.execute(call.name, call.arguments)
                verification_count = len(state.verification_runs)
                repair_count = len(state.repair_rounds)
                state.record_tool_call(call.name, call.arguments, result)
                self.event_handler(
                    "tool_end", {"step": step, "tool": call.name, "result": result}
                )

                if len(state.verification_runs) > verification_count:
                    run = state.verification_runs[-1]
                    self.event_handler(
                        "verification_result", {"step": step, **run.to_dict()}
                    )
                if len(state.repair_rounds) > repair_count:
                    repair = state.repair_rounds[-1]
                    self.event_handler(
                        "repair_started", {"step": step, **repair.to_dict()}
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": self.tools.format_result(result),
                    }
                )

        answer = f"Stopped after reaching the safety limit of {self.max_steps} model steps."
        self.event_handler("finished", {"step": self.max_steps, "status": "step_limit"})
        return build_result("step_limit", answer, self.max_steps)
