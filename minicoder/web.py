"""Local web interface for recording and demonstrating MiniCoder runs."""

from __future__ import annotations

import argparse
import json
import os
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .agent import Agent
from .config import Config
from .evaluation import build_run_record
from .model_client import OpenAICompatibleClient
from .tools import ToolRegistry


MAX_REQUEST_BYTES = 64_000
STATIC_DIR = Path(__file__).with_name("web_static")
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


def resolve_workspace(root: Path, relative_path: str) -> Path:
    """Resolve a browser-supplied workspace while keeping it below root."""
    if not relative_path.strip() or "\x00" in relative_path:
        raise ValueError("Workspace must be a non-empty relative path")
    requested = Path(relative_path)
    if requested.is_absolute():
        raise ValueError("Workspace must be relative to the server root")
    candidate = (root / requested).resolve()
    try:
        common = Path(os.path.commonpath([root, candidate]))
    except ValueError as exc:
        raise ValueError("Workspace is outside the server root") from exc
    if common != root:
        raise ValueError("Workspace is outside the server root")
    if not candidate.is_dir():
        raise ValueError(f"Workspace does not exist: {relative_path}")
    return candidate


def encode_event(event: str, data: dict[str, Any]) -> bytes:
    return (
        json.dumps({"event": event, "data": data}, ensure_ascii=False) + "\n"
    ).encode("utf-8")


class MiniCoderWebServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        root: Path,
        env_file: Path,
    ) -> None:
        super().__init__(address, MiniCoderRequestHandler)
        self.root = root.resolve()
        self.env_file = env_file.resolve()
        self.run_lock = threading.Lock()


class MiniCoderRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: MiniCoderWebServer

    def log_message(self, format: str, *args: Any) -> None:
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(format, *args)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "MiniCoder web console",
                    "root": str(self.server.root),
                },
            )
            return
        static = STATIC_FILES.get(path)
        if static is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        filename, content_type = static
        file_path = STATIC_DIR / filename
        try:
            content = file_path.read_bytes()
        except OSError:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Static asset is unavailable: {filename}"},
            )
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/run":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        if not self.server.run_lock.acquire(blocking=False):
            self._send_json(
                HTTPStatus.CONFLICT,
                {"error": "An agent run is already in progress"},
            )
            return
        try:
            payload = self._read_payload()
            task = str(payload.get("task", "")).strip()
            workspace = resolve_workspace(
                self.server.root, str(payload.get("workspace", "demo_project"))
            )
            max_steps = int(payload.get("max_steps", 15))
            if not task:
                raise ValueError("Task must not be empty")
            if not 1 <= max_steps <= 50:
                raise ValueError("max_steps must be between 1 and 50")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.server.run_lock.release()
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(event: str, data: dict[str, Any]) -> None:
            self.wfile.write(encode_event(event, data))
            self.wfile.flush()

        try:
            workspace_name = workspace.relative_to(self.server.root).as_posix()
            emit(
                "run_started",
                {"workspace": workspace_name, "max_steps": max_steps},
            )
            config = Config.from_env(self.server.env_file)
            agent = Agent(
                client=OpenAICompatibleClient(config),
                tools=ToolRegistry(workspace),
                max_steps=max_steps,
                event_handler=emit,
            )
            result = agent.run(task)
            run_record = build_run_record(task, workspace_name, result)
            emit(
                "final_result",
                {
                    "status": result.status,
                    "answer": result.answer,
                    "steps": result.steps,
                    "duration_seconds": result.duration_seconds,
                    "verification": result.verification.to_dict(),
                    "report": run_record,
                },
            )
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            try:
                emit("run_error", {"error": f"{type(exc).__name__}: {exc}"})
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            self.close_connection = True
            self.server.run_lock.release()

    def _read_payload(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if not 0 < length <= MAX_REQUEST_BYTES:
            raise ValueError(f"Request body must be 1-{MAX_REQUEST_BYTES} bytes")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)


def create_server(root: Path, env_file: Path, port: int = 8765) -> MiniCoderWebServer:
    if not STATIC_DIR.is_dir():
        raise RuntimeError(f"Web assets are missing: {STATIC_DIR}")
    return MiniCoderWebServer(("127.0.0.1", port), root, env_file)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local MiniCoder recording console")
    parser.add_argument("--root", default=".", help="Root containing allowed workspaces")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    env_file = Path(args.env_file).resolve()
    if not root.is_dir():
        print(f"Error: root does not exist: {root}")
        return 2
    try:
        server = create_server(root, env_file, args.port)
    except (OSError, RuntimeError) as exc:
        print(f"Error: {exc}")
        return 2
    url = f"http://127.0.0.1:{server.server_port}"
    print("MiniCoder recording console")
    print(f"Local URL: {url}")
    print(f"Workspace root: {root}")
    print("Press Ctrl+C to stop. API keys remain server-side.")
    if not args.no_browser:
        timer = threading.Timer(0.5, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping MiniCoder web console...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
