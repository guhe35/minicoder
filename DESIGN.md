# MiniCoder design notes

## Control loop

1. Add the system prompt and user task to the message history.
2. Send the history and JSON tool schemas to the model.
3. If the model requests tools, execute each tool locally and append structured results.
4. Send the enlarged history back to the model.
5. Stop on a normal final response or after the configured step limit.

The model decides *which* action to take, while deterministic Python code decides *whether and how* that action is executed.

## Safety boundary

- Every file path is resolved and checked against the workspace root.
- Files larger than 500 KiB are rejected to limit accidental context growth.
- Commands run without a shell, use an executable allowlist, and reject composition, redirection, inline code and unsafe Git subcommands.
- Commands have a timeout and their output is truncated.
- Exact text replacement verifies the expected match count before writing.
- Model failures are retried, and tool failures are returned to the model instead of crashing the loop.

This is risk reduction rather than a complete sandbox. A production version should run commands in an isolated container with resource and network limits.

## Main trade-offs

- Native tool calling gives structured arguments but ties the current adapter to compatible APIs.
- Whole conversation history is simple and easy to explain, but needs summarization for long tasks.
- A conservative command allowlist is safer for the demonstration, but supports fewer build tools.
- `replace_in_file` is predictable for small edits; a unified-diff tool would scale better to complex changes.
