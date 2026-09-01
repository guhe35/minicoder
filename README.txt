MiniCoder：可修复、可验证、可评测的轻量编程智能体

仓库：https://github.com/guhe35/minicoder

简介：MiniCoder直接使用兼容OpenAI格式的原生tool calling，不依赖Agent框架。模型在本地工作区内读取、搜索、写入、精确替换代码并运行开发命令；文件路径限制、命令白名单、超时和最大轮数由确定性Python代码控制。

核心亮点：模型的完成声明不会被直接采信。最后一次修改后必须有成功的测试、构建或运行证据，否则完成门会拒绝结束。系统显式记录失败验证、自修复轮次和完成拒绝，并生成可比较的JSON报告。

配置：复制.env.example为.env，填写DEEPSEEK_API_KEY。API密钥只在Python后端读取。

主项目测试：python -m unittest discover -s tests -v

命令行：python -m minicoder "任务" --workspace showcase_project --report run.json

前端演示：运行python -m minicoder.web并访问http://127.0.0.1:8765。默认任务位于showcase_project，要求Agent先复现9个失败测试，再完成依赖图分层、循环检测、深拷贝、Markdown报告和边界测试。该目录故意保留未完成实现，用于重复录制。

评测：收集多次报告后运行python -m minicoder.evaluation run1.json run2.json，可得到成功率、平均步骤、平均耗时及修复轮次汇总。

限制：目前仅支持兼容Chat Completions工具调用的模型；命令白名单偏保守；长对话尚未自动压缩，生产环境仍应增加容器隔离。
