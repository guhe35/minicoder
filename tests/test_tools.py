from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from minicoder.tools import ToolRegistry


class ToolRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.tools = ToolRegistry(self.root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_write_read_replace_and_search(self) -> None:
        written = self.tools.execute(
            "write_file", {"path": "src/example.py", "content": "value = 1\n"}
        )
        self.assertTrue(written["ok"])

        read = self.tools.execute("read_file", {"path": "src/example.py"})
        self.assertIn("1: value = 1", read["content"])

        replaced = self.tools.execute(
            "replace_in_file",
            {"path": "src/example.py", "old_text": "value = 1", "new_text": "value = 2"},
        )
        self.assertTrue(replaced["ok"])
        self.assertEqual((self.root / "src/example.py").read_text(), "value = 2\n")

        search = self.tools.execute("search_files", {"query": "VALUE", "path": "src"})
        self.assertEqual(search["matches"][0]["line"], 1)

    def test_rejects_path_escape(self) -> None:
        result = self.tools.execute("read_file", {"path": "../secret.txt"})
        self.assertFalse(result["ok"])
        self.assertIn("outside", result["error"])

    def test_replacement_is_atomic_when_count_is_wrong(self) -> None:
        target = self.root / "same.txt"
        target.write_text("same same", encoding="utf-8")
        result = self.tools.execute(
            "replace_in_file",
            {"path": "same.txt", "old_text": "same", "new_text": "new"},
        )
        self.assertFalse(result["ok"])
        self.assertEqual(target.read_text(encoding="utf-8"), "same same")

    def test_run_command_and_reject_shell_operator(self) -> None:
        (self.root / "hello.py").write_text("print('hello-agent')\n", encoding="utf-8")
        result = self.tools.execute("run_command", {"command": "python hello.py"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello-agent", result["output"])

        rejected = self.tools.execute(
            "run_command", {"command": "python hello.py && git status"}
        )
        self.assertFalse(rejected["ok"])

        git_push = self.tools.execute("run_command", {"command": "git push origin main"})
        self.assertFalse(git_push["ok"])
        self.assertIn("subcommand", git_push["error"])


if __name__ == "__main__":
    unittest.main()
