"""Local tools exposed to the language model."""

from __future__ import annotations

import fnmatch
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


MAX_FILE_BYTES = 512_000
MAX_COMMAND_OUTPUT = 12_000
IGNORED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache"}


class ToolError(Exception):
    """An expected, user-readable tool failure."""


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., dict[str, Any]]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Define, validate and execute tools inside one workspace."""

    ALLOWED_EXECUTABLES = {
        "python", "python3", "py", "pytest",
        "node", "npm", "npx", "pnpm", "yarn",
        "git", "go", "cargo", "java", "javac", "mvn", "gradle", "dotnet",
    }
    FORBIDDEN_ARGUMENTS = {
        "-c",  # Blocks arbitrary inline Python code.
        "-e",  # Blocks arbitrary inline Node code.
        "--eval",
    }
    SAFE_GIT_SUBCOMMANDS = {"status", "diff", "log", "show", "rev-parse", "ls-files"}
    FORBIDDEN_COMMAND_FRAGMENTS = {
        "reset --hard", "clean -fd", "checkout --", "format ",
        "shutdown", "remove-item", "rm -", "rmdir", " del ", "erase ",
    }

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        if not self.workspace.is_dir():
            raise ValueError(f"Workspace does not exist: {self.workspace}")
        self._tools = self._build_tools()

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        try:
            return {"ok": True, **tool.handler(**arguments)}
        except (ToolError, TypeError, ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # Keep one broken tool call from crashing the agent.
            return {"ok": False, "error": f"Unexpected tool error: {type(exc).__name__}: {exc}"}

    def _resolve_path(self, relative_path: str, must_exist: bool = False) -> Path:
        if not relative_path or "\x00" in relative_path:
            raise ToolError("Path must be a non-empty string")
        candidate = (self.workspace / relative_path).resolve()
        try:
            common = Path(os.path.commonpath([self.workspace, candidate]))
        except ValueError as exc:
            raise ToolError("Path is outside the workspace") from exc
        if common != self.workspace:
            raise ToolError("Path is outside the workspace")
        if must_exist and not candidate.exists():
            raise ToolError(f"Path does not exist: {relative_path}")
        return candidate

    def _build_tools(self) -> dict[str, Tool]:
        object_schema = {"type": "object", "additionalProperties": False}
        tools = [
            Tool(
                "list_files",
                "List files under a workspace-relative directory.",
                {**object_schema, "properties": {"path": {"type": "string", "default": "."}, "max_files": {"type": "integer", "default": 200}}},
                self.list_files,
            ),
            Tool(
                "read_file",
                "Read a UTF-8 text file with optional 1-based line bounds.",
                {**object_schema, "properties": {"path": {"type": "string"}, "start_line": {"type": "integer", "default": 1}, "end_line": {"type": ["integer", "null"]}}, "required": ["path"]},
                self.read_file,
            ),
            Tool(
                "write_file",
                "Create or replace a UTF-8 text file inside the workspace.",
                {**object_schema, "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
                self.write_file,
            ),
            Tool(
                "replace_in_file",
                "Replace an exact text fragment. By default the old text must occur exactly once.",
                {**object_schema, "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}, "expected_replacements": {"type": "integer", "default": 1}}, "required": ["path", "old_text", "new_text"]},
                self.replace_in_file,
            ),
            Tool(
                "search_files",
                "Search text recursively in workspace files and return matching lines.",
                {**object_schema, "properties": {"query": {"type": "string"}, "path": {"type": "string", "default": "."}, "file_pattern": {"type": "string", "default": "*"}, "max_results": {"type": "integer", "default": 100}}, "required": ["query"]},
                self.search_files,
            ),
            Tool(
                "run_command",
                "Run one non-interactive development command in the workspace. Shell operators and destructive commands are rejected.",
                {**object_schema, "properties": {"command": {"type": "string"}, "timeout_seconds": {"type": "integer", "default": 60}}, "required": ["command"]},
                self.run_command,
            ),
        ]
        return {tool.name: tool for tool in tools}

    def list_files(self, path: str = ".", max_files: int = 200) -> dict[str, Any]:
        root = self._resolve_path(path, must_exist=True)
        if not root.is_dir():
            raise ToolError(f"Not a directory: {path}")
        max_files = max(1, min(max_files, 1000))
        files: list[str] = []
        for item in sorted(root.rglob("*")):
            if any(part in IGNORED_PARTS for part in item.parts):
                continue
            if item.is_file():
                files.append(item.relative_to(self.workspace).as_posix())
                if len(files) >= max_files:
                    break
        return {"files": files, "truncated": len(files) >= max_files}

    def read_file(
        self, path: str, start_line: int = 1, end_line: int | None = None
    ) -> dict[str, Any]:
        file_path = self._resolve_path(path, must_exist=True)
        if not file_path.is_file():
            raise ToolError(f"Not a file: {path}")
        if file_path.stat().st_size > MAX_FILE_BYTES:
            raise ToolError(f"File is too large to read (limit {MAX_FILE_BYTES} bytes)")
        if start_line < 1 or (end_line is not None and end_line < start_line):
            raise ToolError("Invalid line range")
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise ToolError("Only UTF-8 text files are supported") from exc
        selected = lines[start_line - 1 : end_line]
        numbered = "\n".join(
            f"{number}: {line}" for number, line in enumerate(selected, start=start_line)
        )
        return {"path": path, "content": numbered, "total_lines": len(lines)}

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        file_path = self._resolve_path(path)
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ToolError(f"Content is too large (limit {MAX_FILE_BYTES} bytes)")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return {"path": path, "bytes_written": len(content.encode("utf-8"))}

    def replace_in_file(
        self,
        path: str,
        old_text: str,
        new_text: str,
        expected_replacements: int = 1,
    ) -> dict[str, Any]:
        file_path = self._resolve_path(path, must_exist=True)
        if not old_text:
            raise ToolError("old_text must not be empty")
        content = file_path.read_text(encoding="utf-8")
        actual = content.count(old_text)
        if actual != expected_replacements:
            raise ToolError(
                f"Expected {expected_replacements} occurrence(s), found {actual}; no changes made"
            )
        updated = content.replace(old_text, new_text, expected_replacements)
        if len(updated.encode("utf-8")) > MAX_FILE_BYTES:
            raise ToolError(f"Updated file is too large (limit {MAX_FILE_BYTES} bytes)")
        file_path.write_text(updated, encoding="utf-8")
        return {"path": path, "replacements": expected_replacements}

    def search_files(
        self,
        query: str,
        path: str = ".",
        file_pattern: str = "*",
        max_results: int = 100,
    ) -> dict[str, Any]:
        if not query:
            raise ToolError("Search query must not be empty")
        root = self._resolve_path(path, must_exist=True)
        max_results = max(1, min(max_results, 500))
        matches: list[dict[str, Any]] = []
        candidates = [root] if root.is_file() else root.rglob("*")
        for file_path in candidates:
            if not file_path.is_file() or any(part in IGNORED_PARTS for part in file_path.parts):
                continue
            if not fnmatch.fnmatch(file_path.name, file_pattern):
                continue
            if file_path.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for line_number, line in enumerate(lines, start=1):
                if query.lower() in line.lower():
                    matches.append({
                        "path": file_path.relative_to(self.workspace).as_posix(),
                        "line": line_number,
                        "text": line[:500],
                    })
                    if len(matches) >= max_results:
                        return {"matches": matches, "truncated": True}
        return {"matches": matches, "truncated": False}

    def run_command(self, command: str, timeout_seconds: int = 60) -> dict[str, Any]:
        tokens = self._validate_command(command)
        timeout_seconds = max(1, min(timeout_seconds, 300))
        try:
            completed = subprocess.run(
                tokens,
                cwd=self.workspace,
                shell=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=timeout_seconds,
            )
            combined = (completed.stdout or "") + (completed.stderr or "")
            truncated = len(combined) > MAX_COMMAND_OUTPUT
            if truncated:
                combined = combined[:MAX_COMMAND_OUTPUT] + "\n... output truncated ..."
            return {
                "command": command,
                "exit_code": completed.returncode,
                "output": combined,
                "truncated": truncated,
            }
        except subprocess.TimeoutExpired as exc:
            partial = (exc.stdout or "") + (exc.stderr or "")
            raise ToolError(
                f"Command timed out after {timeout_seconds}s. Partial output: {partial[:2000]}"
            ) from exc

    def _validate_command(self, command: str) -> list[str]:
        if not command or "\n" in command or "\r" in command:
            raise ToolError("Command must be one non-empty line")
        if any(operator in command for operator in ("&&", "||", ";", "|", ">", "<", "`", "$(")):
            raise ToolError("Shell operators and redirection are not allowed")
        lowered = f" {command.lower()} "
        if any(fragment in lowered for fragment in self.FORBIDDEN_COMMAND_FRAGMENTS):
            raise ToolError("Potentially destructive command is not allowed")
        try:
            tokens = shlex.split(command, posix=os.name != "nt")
        except ValueError as exc:
            raise ToolError(f"Cannot parse command: {exc}") from exc
        tokens = [token.strip("\"'") for token in tokens]
        if not tokens:
            raise ToolError("Command is empty")
        executable = Path(tokens[0].strip("\"'")).stem.lower()
        if executable not in self.ALLOWED_EXECUTABLES:
            allowed = ", ".join(sorted(self.ALLOWED_EXECUTABLES))
            raise ToolError(f"Executable '{executable}' is not allowed. Allowed: {allowed}")
        if executable in {"python", "python3", "py", "node"}:
            lowered_tokens = {token.lower() for token in tokens[1:]}
            if lowered_tokens & self.FORBIDDEN_ARGUMENTS:
                raise ToolError("Inline code evaluation is not allowed")
        if executable == "git":
            subcommand = tokens[1].lower() if len(tokens) > 1 else ""
            if subcommand not in self.SAFE_GIT_SUBCOMMANDS:
                allowed = ", ".join(sorted(self.SAFE_GIT_SUBCOMMANDS))
                raise ToolError(f"Git subcommand '{subcommand}' is not allowed. Allowed: {allowed}")
        return tokens

    @staticmethod
    def format_result(result: dict[str, Any]) -> str:
        return json.dumps(result, ensure_ascii=False)
