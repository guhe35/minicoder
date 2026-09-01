# MiniCoder design notes

## Control loop

1. Add the system prompt and user task to the message history.
2. Send the history and JSON tool schemas to the model.
3. If the model requests tools, execute each tool locally and append structured results.
4. Send the enlarged history back to the model.
5. If files changed, require successful test/build/execution evidence after the latest edit.
6. Reject an unsupported completion attempt and feed the deterministic reason back to the model.
7. Stop with `verified`, finish a read-only task with `completed`, or hit the step limit.

The model decides *which* action to take, while deterministic Python code decides *whether and how* that action is executed.

## Evidence-gated completion

`verification.py` records changed files and recognized verification commands using a monotonic tool-call sequence. A successful check is valid only when it occurs after the latest edit. A model cannot finish merely by claiming success: missing, stale, or failed evidence produces controller feedback and another model turn.

The final CLI report lists changed files, verification runs, the latest exit code, and model/tool-call counts. Recognized evidence includes common test commands (`pytest`, `unittest`, npm, Maven, Gradle, Cargo, Go and .NET), build checks, and direct Python/Node/Java execution. Read-only tasks do not require post-change verification.

When DeepSeek thinking mode is enabled, every assistant message preserves its
`reasoning_content` field and replays it unchanged with later tool-result requests,
as required by the DeepSeek Chat Completions protocol.

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
