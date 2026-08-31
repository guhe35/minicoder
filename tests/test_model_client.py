import unittest

from minicoder.model_client import OpenAICompatibleClient


class ModelResponseParsingTests(unittest.TestCase):
    def test_parses_native_tool_call(self) -> None:
        response = OpenAICompatibleClient._parse_response(
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
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
