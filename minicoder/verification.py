"""Deterministic completion checks for code-changing agent runs."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


EDIT_TOOLS = {"write_file", "replace_in_file"}


def classify_verification_command(command: str) -> str | None:
    """Return the evidence kind for a recognized test, build or run command."""
    try:
        tokens = shlex.split(command, posix=os.name != "nt")
    except ValueError:
        return None
    tokens = [token.strip("\"'") for token in tokens]
    if not tokens:
        return None

    executable = Path(tokens[0]).stem.lower()
    arguments = [token.lower() for token in tokens[1:]]

    if executable == "pytest":
        return "test"
    if executable in {"python", "python3", "py"}:
        if len(arguments) >= 2 and arguments[0] == "-m":
            if arguments[1] in {"pytest", "unittest"}:
                return "test"
        if any(argument.endswith(".py") for argument in arguments):
            return "execution"
    if executable == "node" and any(
        argument.endswith((".js", ".mjs", ".cjs")) for argument in arguments
    ):
        return "execution"
    if executable in {"npm", "pnpm", "yarn"}:
        if any(argument == "test" or argument.startswith("test:") for argument in arguments):
            return "test"
    if executable == "npx" and arguments:
        if arguments[0] in {"jest", "vitest", "mocha", "playwright"}:
            return "test"
    if executable in {"cargo", "go", "dotnet"} and "test" in arguments:
        return "test"
    if executable == "mvn" and any(
        argument in {"test", "verify"} for argument in arguments
    ):
        return "test"
    if executable == "gradle" and any(
        argument.rsplit(":", 1)[-1] in {"test", "check"} for argument in arguments
    ):
        return "test"
    if executable == "javac":
        return "build"
    if executable in {"mvn", "gradle", "cargo", "go", "dotnet"} and any(
        argument.rsplit(":", 1)[-1] in {"build", "compile", "package", "check"}
        for argument in arguments
    ):
        return "build"
    if executable == "java" and arguments:
        return "execution"
    return None


@dataclass(frozen=True)
class VerificationRun:
    command: str
    kind: str
    exit_code: int | None
    sequence: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "kind": self.kind,
            "exit_code": self.exit_code,
            "passed": self.exit_code == 0,
            "sequence": self.sequence,
        }


@dataclass(frozen=True)
class CompletionCheck:
    allowed: bool
    status: str
    reason: str


@dataclass(frozen=True)
class RepairRound:
    """A code edit made in response to a failed verification command."""

    number: int
    failed_command: str
    failed_exit_code: int | None
    changed_file: str
    sequence: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "failed_command": self.failed_command,
            "failed_exit_code": self.failed_exit_code,
            "changed_file": self.changed_file,
            "sequence": self.sequence,
        }


@dataclass(frozen=True)
class VerificationReport:
    status: str
    changed_files: list[str]
    verification_runs: list[VerificationRun]
    model_calls: int
    tool_calls: int
    repair_rounds: list[RepairRound]
    completion_rejections: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "changed_files": self.changed_files,
            "verification_runs": [run.to_dict() for run in self.verification_runs],
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "successful_verifications": sum(
                run.exit_code == 0 for run in self.verification_runs
            ),
            "failed_verifications": sum(
                run.exit_code != 0 for run in self.verification_runs
            ),
            "repair_rounds": [repair.to_dict() for repair in self.repair_rounds],
            "completion_rejections": self.completion_rejections,
            "reason": self.reason,
        }

    def format_text(self) -> str:
        files = ", ".join(self.changed_files) if self.changed_files else "none"
        lines = [
            f"Verification: {self.status}",
            f"Changed files: {files}",
            f"Model calls: {self.model_calls}; tool calls: {self.tool_calls}",
            (
                f"Failed verifications: "
                f"{sum(run.exit_code != 0 for run in self.verification_runs)}; "
                f"repair rounds: {len(self.repair_rounds)}; "
                f"completion rejections: {self.completion_rejections}"
            ),
        ]
        if self.verification_runs:
            lines.append("Evidence trail:")
            for run in self.verification_runs:
                lines.append(
                    f"- [{run.kind}] {run.command} (exit code {run.exit_code})"
                )
        lines.append(f"Reason: {self.reason}")
        return "\n".join(lines)


@dataclass
class ExecutionState:
    changed_files: set[str] = field(default_factory=set)
    verification_runs: list[VerificationRun] = field(default_factory=list)
    last_change_sequence: int | None = None
    model_calls: int = 0
    tool_calls: int = 0
    repair_rounds: list[RepairRound] = field(default_factory=list)
    completion_rejections: int = 0
    _sequence: int = 0
    _pending_failed_verification: VerificationRun | None = None

    def record_model_call(self) -> None:
        self.model_calls += 1

    def record_tool_call(
        self, name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> None:
        self.tool_calls += 1
        self._sequence += 1

        if name in EDIT_TOOLS and result.get("ok"):
            path = result.get("path") or arguments.get("path")
            if path:
                self.changed_files.add(str(path))
                if self._pending_failed_verification is not None:
                    failed = self._pending_failed_verification
                    self.repair_rounds.append(
                        RepairRound(
                            number=len(self.repair_rounds) + 1,
                            failed_command=failed.command,
                            failed_exit_code=failed.exit_code,
                            changed_file=str(path),
                            sequence=self._sequence,
                        )
                    )
                    self._pending_failed_verification = None
            self.last_change_sequence = self._sequence

        if name == "run_command":
            command = str(result.get("command") or arguments.get("command") or "")
            kind = classify_verification_command(command)
            if kind is not None:
                exit_code = result.get("exit_code") if result.get("ok") else None
                run = VerificationRun(command, kind, exit_code, self._sequence)
                self.verification_runs.append(run)
                self._pending_failed_verification = run if exit_code != 0 else None

    def record_completion_rejection(self) -> None:
        self.completion_rejections += 1

    def check_completion(self) -> CompletionCheck:
        if not self.changed_files:
            return CompletionCheck(
                True,
                "completed",
                "No files were modified, so post-change verification is not required.",
            )

        assert self.last_change_sequence is not None
        current_runs = [
            run for run in self.verification_runs if run.sequence > self.last_change_sequence
        ]
        if not current_runs:
            return CompletionCheck(
                False,
                "unverified",
                "Files were modified, but no recognized verification command ran after the latest change.",
            )

        latest = current_runs[-1]
        if latest.exit_code != 0:
            return CompletionCheck(
                False,
                "unverified",
                f"The latest verification command failed with exit code {latest.exit_code}.",
            )
        return CompletionCheck(
            True,
            "verified",
            f"The latest code changes were verified by `{latest.command}`.",
        )

    def build_report(self) -> VerificationReport:
        check = self.check_completion()
        return VerificationReport(
            status=check.status if check.allowed else "unverified",
            changed_files=sorted(self.changed_files),
            verification_runs=list(self.verification_runs),
            model_calls=self.model_calls,
            tool_calls=self.tool_calls,
            repair_rounds=list(self.repair_rounds),
            completion_rejections=self.completion_rejections,
            reason=check.reason,
        )
