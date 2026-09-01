# MiniCoder

MiniCoder 是一个轻量级编程智能体，可在指定工作区内自主读取代码、修改文件、运行测试，并根据失败结果继续修复。项目使用原生 Tool Calling 实现，不依赖第三方 Agent 框架。

## Git 仓库

https://github.com/guhe35/minicoder

## 如何运行

环境要求：Python 3.10 及以上，无第三方运行依赖。

1. 在项目根目录配置 `.env`，填写 `MODEL_API_KEY`，不要提交真实密钥。
2. 运行 Agent 自身测试：

```bash
python -m unittest discover -s tests -v
```

3. 命令行运行：

```bash
python -m minicoder "任务描述" --workspace showcase_project --report run.json
```

4. 启动前端：

```bash
python -m minicoder.web --port 8765
```

浏览器访问 `http://127.0.0.1:8765/`，填写任务后即可观察完整执行过程。

## 特色功能

- 自主调用文件读取、代码搜索、写入、精确替换和命令执行工具。
- 通过工作区边界、命令白名单、超时和步骤上限约束模型行为。
- 设置验证证据门禁：修改代码后必须通过最新测试、构建或运行验证，才能结束任务。
- 记录验证失败、修复轮次和完成拒绝，前端实时展示执行轨迹。
- 生成 JSON 运行报告，并支持汇总多次运行的成功率、步骤数和修复次数。

## 演示项目

`showcase_project` 是依赖感知的 Sprint 任务调度器。基线代码故意保留 9 个失败测试，供 Agent 演示依赖分层、循环检测、深拷贝、Markdown 报告生成和边界测试补充。需要重复演示时，可用 Git 基线标签恢复：

```bash
git restore --source=showcase-baseline --staged --worktree -- showcase_project
```

