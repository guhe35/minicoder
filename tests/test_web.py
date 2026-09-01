from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from minicoder.web import create_server, encode_event, resolve_workspace


class WebConsoleTests(unittest.TestCase):
    def test_workspace_must_stay_below_server_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "demo"
            workspace.mkdir()
            self.assertEqual(resolve_workspace(root, "demo"), workspace.resolve())
            with self.assertRaises(ValueError):
                resolve_workspace(root, "../outside")
            with self.assertRaises(ValueError):
                resolve_workspace(root, str(workspace.resolve()))

    def test_event_encoding_uses_one_ndjson_record(self) -> None:
        encoded = encode_event("tool_end", {"ok": True, "text": "中文"})
        self.assertTrue(encoded.endswith(b"\n"))
        payload = json.loads(encoded.decode("utf-8"))
        self.assertEqual(payload["event"], "tool_end")
        self.assertEqual(payload["data"]["text"], "中文")

    def test_serves_interface_and_health_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = create_server(root, root / ".env", port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(f"{base_url}/", timeout=3) as response:
                    html = response.read().decode("utf-8")
                with urlopen(f"{base_url}/api/health", timeout=3) as response:
                    health = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
            self.assertIn("基于执行证据的编程智能体", html)
            self.assertTrue(health["ok"])


if __name__ == "__main__":
    unittest.main()
