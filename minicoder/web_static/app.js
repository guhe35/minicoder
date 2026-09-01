const $ = (selector) => document.querySelector(selector);

const form = $("#run-form");
const runButton = $("#run-button");
const runLabel = $("#run-label");
const clearButton = $("#clear-button");
const downloadButton = $("#download-report");
const traceList = $("#trace-list");
const traceEmpty = $("#trace-empty");
const traceTemplate = $("#trace-template");
const systemState = $("#system-state");
const systemLabel = $("#system-label");
const verdict = $("#verdict");
const elapsed = $("#elapsed");

let startedAt = null;
let timer = null;
let lastRunReport = null;

const STATUS_LABELS = {
  idle: "尚未运行",
  running: "运行中",
  verified: "验证通过",
  completed: "已完成",
  unverified: "未通过验证",
  step_limit: "达到轮数上限",
  error: "运行错误",
};
const EVIDENCE_LABELS = { test: "测试", build: "构建", execution: "运行" };
const TOOL_LABELS = {
  list_files: "列出文件 · list_files",
  read_file: "读取文件 · read_file",
  write_file: "写入文件 · write_file",
  replace_in_file: "替换代码 · replace_in_file",
  search_files: "搜索代码 · search_files",
  run_command: "运行命令 · run_command",
};

function translateReason(reason = "") {
  if (reason.startsWith("No files were modified")) return "本次任务没有修改文件，因此不需要执行修改后验证。";
  if (reason.startsWith("Files were modified, but no recognized")) return "文件已经修改，但最新修改之后尚未运行可识别的验证命令。";
  const failed = reason.match(/failed with exit code (.+)\.$/);
  if (failed) return `最新验证命令执行失败，退出码为 ${failed[1]}。`;
  const verified = reason.match(/verified by `(.+)`\.$/);
  if (verified) return `最新代码修改已通过命令 ${verified[1]} 验证。`;
  return reason;
}

function setSystemState(state, label) {
  systemState.dataset.state = state;
  systemLabel.textContent = label;
}

function setVerdict(state, label) {
  verdict.dataset.state = state;
  verdict.textContent = label;
}

function formatElapsed() {
  if (!startedAt) return "00:00";
  const seconds = Math.floor((Date.now() - startedAt) / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function resetTrace() {
  traceList.replaceChildren();
  traceEmpty.hidden = false;
  $("#model-calls").textContent = "—";
  $("#tool-calls").textContent = "—";
  $("#changed-files").innerHTML = '<span class="muted">暂无修改</span>';
  $("#evidence-list").innerHTML = '<span class="muted">验证命令及退出码将在这里记录。</span>';
  ["result-steps", "result-duration", "failed-verifications", "repair-rounds", "completion-rejections"]
    .forEach((id) => { $(`#${id}`).textContent = "—"; });
  $("#repair-list").replaceChildren();
  $("#repair-history").hidden = true;
  $("#final-answer").hidden = true;
  lastRunReport = null;
  downloadButton.disabled = true;
  setVerdict("idle", STATUS_LABELS.idle);
  elapsed.textContent = "00:00";
}

function compact(value, limit = 170) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}

function addTrace(kind, label, title, summary, payload = null) {
  traceEmpty.hidden = true;
  const item = traceTemplate.content.firstElementChild.cloneNode(true);
  item.dataset.kind = kind;
  item.querySelector(".trace-kind").textContent = label;
  item.querySelector(".trace-time").textContent = formatElapsed();
  item.querySelector(".trace-title").textContent = title;
  item.querySelector(".trace-summary").textContent = summary;
  if (payload !== null) {
    const details = item.querySelector(".trace-details");
    details.hidden = false;
    details.querySelector("pre").textContent = JSON.stringify(payload, null, 2);
  }
  traceList.append(item);
  traceList.scrollTop = traceList.scrollHeight;
}

function renderReport(result) {
  const report = result.verification;
  setVerdict(result.status, STATUS_LABELS[result.status] || result.status);
  $("#model-calls").textContent = report.model_calls;
  $("#tool-calls").textContent = report.tool_calls;
  $("#result-steps").textContent = result.steps;
  $("#result-duration").textContent = `${Number(result.duration_seconds || 0).toFixed(1)}s`;
  $("#failed-verifications").textContent = report.failed_verifications ?? report.verification_runs.filter((run) => run.exit_code !== 0).length;
  $("#repair-rounds").textContent = report.repair_rounds?.length || 0;
  $("#completion-rejections").textContent = report.completion_rejections || 0;

  const files = $("#changed-files");
  files.replaceChildren();
  if (!report.changed_files.length) {
    const none = document.createElement("span");
    none.className = "muted";
    none.textContent = "没有修改文件";
    files.append(none);
  } else {
    report.changed_files.forEach((path) => {
      const chip = document.createElement("span");
      chip.className = "file-chip";
      chip.textContent = path;
      files.append(chip);
    });
  }

  const evidenceList = $("#evidence-list");
  evidenceList.replaceChildren();
  if (!report.verification_runs.length) {
    const none = document.createElement("span");
    none.className = "muted";
    none.textContent = "本次任务不需要修改后验证";
    evidenceList.append(none);
  } else {
    report.verification_runs.forEach((run, index) => {
      const row = document.createElement("div");
      row.className = "evidence-run";
      const type = document.createElement("span");
      type.className = "evidence-type";
      type.textContent = `${index + 1} · ${EVIDENCE_LABELS[run.kind] || run.kind}`;
      const command = document.createElement("span");
      command.className = "evidence-code";
      command.textContent = run.command;
      const exit = document.createElement("span");
      exit.className = `evidence-exit${run.exit_code === 0 ? "" : " failed"}`;
      exit.textContent = `退出码 ${run.exit_code}`;
      row.append(type, command, exit);
      evidenceList.append(row);
    });
  }

  const repairHistory = $("#repair-history");
  const repairList = $("#repair-list");
  repairList.replaceChildren();
  if (report.repair_rounds?.length) {
    report.repair_rounds.forEach((repair) => {
      const row = document.createElement("div");
      row.className = "repair-row";
      row.textContent = `第 ${repair.number} 次修复：${repair.failed_command} 失败后修改 ${repair.changed_file}`;
      repairList.append(row);
    });
    repairHistory.hidden = false;
  } else {
    repairHistory.hidden = true;
  }

  $("#answer-text").textContent = result.answer;
  $("#reason-text").textContent = translateReason(report.reason);
  $("#final-answer").hidden = false;
  lastRunReport = result.report || null;
  downloadButton.disabled = !lastRunReport;
}

function handleEvent(message) {
  const { event, data } = message;
  if (event === "run_started") {
    addTrace("tool", "任务启动", "智能体开始运行", `工作区：${data.workspace} · 安全上限：${data.max_steps} 轮`);
  } else if (event === "model_request") {
    addTrace("model", `第 ${data.step} 轮`, "模型正在决策", "正在发送任务、工具定义和已有执行历史。");
  } else if (event === "tool_start") {
    addTrace("tool", `第 ${data.step} 轮`, TOOL_LABELS[data.tool] || data.tool, compact(data.arguments), data.arguments);
  } else if (event === "tool_end") {
    const ok = Boolean(data.result?.ok);
    addTrace(ok ? "success" : "error", ok ? "工具结果" : "工具错误", `${TOOL_LABELS[data.tool] || data.tool}${ok ? "执行成功" : "执行失败"}`, compact(data.result), data.result);
  } else if (event === "verification_result") {
    const passed = data.exit_code === 0;
    if (!passed) setVerdict("unverified", "验证失败，等待修复");
    addTrace(
      passed ? "success" : "error",
      passed ? "验证通过" : "验证失败",
      data.command,
      passed ? "当前代码通过验证，可作为完成证据。" : `退出码 ${data.exit_code}，智能体将根据输出继续处理。`,
      data,
    );
  } else if (event === "repair_started") {
    setVerdict("running", `第 ${data.number} 次修复`);
    addTrace("warning", `修复轮次 ${data.number}`, "根据失败验证修改代码", `${data.failed_command} 失败后修改 ${data.changed_file}`, data);
  } else if (event === "completion_rejected") {
    setVerdict("unverified", "完成请求被拒绝");
    addTrace("warning", `第 ${data.step} 轮`, "完成请求被验证门拒绝", translateReason(data.reason));
  } else if (event === "finished") {
    addTrace(data.status === "verified" ? "success" : "model", "控制器", `任务结束：${STATUS_LABELS[data.status] || data.status}`, `智能体在第 ${data.step} 轮后停止。`);
  } else if (event === "final_result") {
    renderReport(data);
  } else if (event === "run_error") {
    throw new Error(`服务端错误：${data.error}`);
  }
}

async function readEventStream(response) {
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      message = body.error || message;
    } catch (_) {}
    throw new Error(message);
  }
  if (!response.body) throw new Error("当前浏览器不支持流式响应");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    lines.filter(Boolean).forEach((line) => handleEvent(JSON.parse(line)));
    if (done) break;
  }
  if (buffer.trim()) handleEvent(JSON.parse(buffer));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = $("#task").value.trim();
  const workspace = $("#workspace").value.trim();
  const maxSteps = Number($("#max-steps").value);
  if (!task || !workspace) {
    addTrace("error", "输入检查", "缺少必要信息", "请填写编程任务和工作区。");
    return;
  }
  resetTrace();
  startedAt = Date.now();
  timer = window.setInterval(() => { elapsed.textContent = formatElapsed(); }, 500);
  runButton.disabled = true;
  runLabel.textContent = "智能体运行中";
  setSystemState("running", "正在运行");
  setVerdict("running", STATUS_LABELS.running);
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task, workspace, max_steps: maxSteps }),
    });
    await readEventStream(response);
    setSystemState("ready", "本地服务就绪");
  } catch (error) {
    setSystemState("error", "运行错误");
    setVerdict("error", STATUS_LABELS.error);
    addTrace("error", "运行错误", "智能体运行失败", error.message || String(error));
  } finally {
    window.clearInterval(timer);
    elapsed.textContent = formatElapsed();
    runButton.disabled = false;
    runLabel.textContent = "运行智能体";
  }
});

downloadButton.addEventListener("click", () => {
  if (!lastRunReport) return;
  const blob = new Blob([`${JSON.stringify(lastRunReport, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `minicoder-report-${lastRunReport.run_id.slice(0, 8)}.json`;
  link.click();
  URL.revokeObjectURL(url);
});

clearButton.addEventListener("click", () => { if (!runButton.disabled) resetTrace(); });

fetch("/api/health")
  .then((response) => {
    if (!response.ok) throw new Error("健康检查失败");
    return response.json();
  })
  .then(() => setSystemState("ready", "本地服务就绪"))
  .catch(() => setSystemState("error", "服务离线"));
