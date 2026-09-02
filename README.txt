# MiniCoder

该项目是一个轻量级编程智能体，使用 Python 标准库和原生 Tool Calling 实现，不依赖第三方 Agent 框架。它能够理解用户给出的编程任务，在指定工作区内读取、搜索和修改代码，主动运行测试，并根据失败信息继续修复。项目重点解决大模型生成代码后缺少安全约束、完成条件不可靠和执行过程难以观察的问题。

## Git 仓库

https://github.com/guhe35/minicoder

## 如何运行

环境要求：Python 3.10 及以上，无第三方运行依赖。在项目根目录配置 `.env`：

```text
MODEL_API_URL=<兼容 Chat Completions 的接口地址>
MODEL_API_KEY=<API Key>
MODEL_NAME=<模型名称>
```

请勿提交或展示真实密钥。首先运行 Agent 自身测试：

```bash
python -m unittest discover -s tests -v
```

命令行执行任务并保存 JSON 报告：

```bash
python -m minicoder "任务描述" --workspace showcase_project --report run.json
```

启动可视化前端：

```bash
python -m minicoder.web --port 8765
```

启动前端后，浏览器访问该网页，即可填写任务、设置工作目录，并实时查看模型响应、工具调用、文件修改、测试证据和最终结果。

## 执行流程

模型客户端向兼容接口发送任务上下文和工具定义，并解析模型返回的工具调用。Agent 核心负责维护“模型决策—工具执行—结果反馈”的循环。工具结果会重新加入上下文，模型据此选择下一步操作，直到任务完成或达到最大步骤数。系统支持文件列表、读取、搜索、写入、精确替换和命令执行，可覆盖常见的小型代码维护任务。

## 特色功能

- 安全执行：所有路径必须位于指定工作区，命令经过白名单检查，并受到超时、输出长度和最大步骤限制。
- 验证证据门禁：代码修改后必须重新运行有效的测试、构建或示例命令。最新验证失败或已经过期时，系统会拒绝模型的完成声明。
- 可观察的自我修复：系统记录失败验证、后续代码修改、修复轮次和完成拒绝，便于区分一次生成与基于错误反馈的持续修复。
- 前端与评测：Web 页面实时展示执行轨迹和验证状态；单次运行可导出 JSON 报告，多次报告可汇总成功率、执行步骤、耗时和修复次数。

## 演示说明

`showcase_project` 是依赖感知的 Sprint 任务调度器。基线代码故意保留 10 项测试中的 9 项失败，用于演示 Agent 复现问题、实现依赖分层与循环检测、生成 Markdown 报告、补充边界测试并完成最终验证。重复演示前可恢复基线：

```bash
git restore --source=showcase-baseline --staged --worktree -- showcase_project
```
