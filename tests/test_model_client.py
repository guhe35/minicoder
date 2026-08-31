from io import BytesIO
import unittest
import urllib.error
from unittest.mock import patch

from minicoder.config import Config
from minicoder.model_client import OpenAICompatibleClient


class ModelResponseParsingTests(unittest.TestCase):
    def test_parses_native_tool_call(self) -> None:
        response = OpenAICompatibleClient._parse_response(
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "reasoning_content": "I should inspect the file first.",
                            "tool_calls": [
                                {
                                    "id": "call_7",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": '{"path":"main.py"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        )
        self.assertEqual(response.tool_calls[0].name, "read_file")
        self.assertEqual(response.tool_calls[0].arguments, {"path": "main.py"})
        self.assertEqual(response.raw_tool_calls[0]["id"], "call_7")
        self.assertEqual(
            response.reasoning_content, "I should inspect the file first."
        )

    def test_builds_deepseek_thinking_payload_without_temperature(self) -> None:
        client = OpenAICompatibleClient(
            Config(
                api_url="https://api.deepseek.com/chat/completions",
                api_key="sk-test",
                model="deepseek-v4-pro",
                thinking_mode="enabled",
                reasoning_effort="high",
            )
        )
        payload = client._build_payload([{"role": "user", "content": "hi"}], [])
        self.assertEqual(payload["thinking"], {"type": "enabled"})
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertFalse(payload["stream"])
        self.assertNotIn("temperature", payload)

    def test_disabled_thinking_omits_reasoning_effort(self) -> None:
        client = OpenAICompatibleClient(
            Config(
                api_url="https://api.deepseek.com/chat/completions",
                api_key="sk-test",
                model="deepseek-v4-pro",
                thinking_mode="disabled",
                reasoning_effort="high",
            )
        )
        payload = client._build_payload([], [])
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", payload)

    def test_http_400_includes_provider_error_body(self) -> None:
        client = OpenAICompatibleClient(
            Config(
                api_url="https://api.deepseek.com/chat/completions",
                api_key="sk-test",
                model="deepseek-v4-pro",
                max_retries=0,
            )
        )
        error = urllib.error.HTTPError(
            client.config.api_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=BytesIO(b'{"error":{"message":"missing reasoning_content"}}'),
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "missing reasoning_content"):
                client.complete([{"role": "user", "content": "hi"}], [])

    def test_rejects_malformed_tool_arguments(self) -> None:
        with self.assertRaises(RuntimeError):
            OpenAICompatibleClient._parse_response(
                {
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "id": "broken",
                                        "function": {
                                            "name": "read_file",
                                            "arguments": "not-json",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
