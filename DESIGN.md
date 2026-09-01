# MiniCoder design notes

## Control loop

MiniCoder uses a model-tool-model loop without an agent framework:

1. Send the task, message history and JSON tool schemas to the model.
2. Execute requested tools inside the selected workspace.
3. Return structured tool results to the model instead of inventing outcomes.
4. Record edits and recognized test, build or execution commands.
5. If verification fails, expose the failure and wait for a subsequent edit.
6. Count that edit as a repair round, then require fresh verification.
7. Accept completion only when evidence after the latest edit succeeds.

DeepSeek thinking-mode assistant messages preserve and replay
`reasoning_content` as required by its Chat Completions protocol.

## Evidence-gated completion and observable repair

`verification.py` uses a monotonic tool-call sequence. Verification before the
latest edit is stale. Missing, stale or failed evidence makes the controller
reject the model's completion request and add a deterministic explanation to
the next model turn.

A failed verification becomes pending repair state. The first successful code
edit after it creates a `RepairRound` containing the failed command, exit code,
changed file and sequence number. A later successful check closes the loop.
This deliberately distinguishes a real repair from simply rerunning a command.

The Agent emits dedicated `verification_result`, `repair_started` and
`completion_rejected` events. Both CLI and Web UI consume the same event stream.

## Structured reports and evaluation

Every run can produce a `minicoder.run-report.v1` JSON record containing task,
workspace, outcome, steps, duration, changed files, all verification commands,
repair rounds and completion rejections. The browser downloads the same schema
that `--report` writes from the CLI.

`evaluation.py` aggregates one or more reports into reproducible metrics:
success rate, verified runs, average steps, average duration, failed
verifications, repair rounds and completion rejections. This is intentionally
small: it measures observed runs without claiming that a tiny demo suite is a
general coding benchmark.

## Safety boundary

- File paths are resolved below the workspace root.
- Large files and oversized command output are limited.
- Commands run without a shell, use an allowlist and reject composition,
  redirection, inline code and unsafe Git subcommands.
- Commands have timeouts; exact replacement checks occurrence count.
- Model failures are retried; tool errors return to the model.
- Web workspaces must remain below the server root and only one run is active.
- API credentials stay in the local Python process.

This reduces risk but is not a complete sandbox. Production execution should
use an isolated container with resource, process and network limits.

## Main trade-offs

- Whole-history replay is transparent but needs summarization for long tasks.
- A conservative command allowlist is safer but supports fewer toolchains.
- Exact replacement is predictable for demos; unified diffs scale better.
- Repair rounds use observable test/edit order rather than model self-report,
  but they do not semantically prove that an edit addressed the failure.
