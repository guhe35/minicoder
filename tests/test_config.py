from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from minicoder.config import Config, load_dotenv


class ConfigTests(unittest.TestCase):
    def test_placeholder_configuration_is_rejected(self) -> None:
        config = Config(
            api_url="https://YOUR_PROVIDER.example/v1/chat/completions",
            api_key="YOUR_API_KEY_HERE",
            model="YOUR_MODEL_NAME_HERE",
        )
        with self.assertRaises(ValueError):
            config.validate()

    def test_dotenv_does_not_override_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("MODEL_NAME=from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {"MODEL_NAME": "from-process"}, clear=False):
                load_dotenv(env_file)
                self.assertEqual(os.environ["MODEL_NAME"], "from-process")


if __name__ == "__main__":
    unittest.main()

