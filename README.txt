MiniCoder：可修复、可验证、可评测的轻量编程智能体

仓库：https://github.com/guhe35/minicoder

简介：MiniCoder直接使用兼容OpenAI格式的原生tool calling，不依赖Agent框架。模型在本地工作区内读取、搜索、写入、精确替换代码并运行开发命令；文件路径限制、命令白名单、超时和最大轮数由确定性Python代码控制。

核心亮点：代码修改后，模型的完成声明不会被直接采信。最后一次修改之后必须有成功的测试、构建或运行证据，否则完成门会拒绝结束。测试失败后，Agent根据真实输出继续修改；系统记录失败验证、修复轮次和完成拒绝次数，并生成可比较的结构化报告。

配置：复制.env.example为.env，填写DEEPSEEK_API_KEY。API地址、模型和思考模式均由.env配置，密钥只在Python后端读取。

测试：python -m unittest discover -s tests -v

命令行：python -m minicoder "任务" --workspace demo_project --report run.json

前端：python -m minicoder.web，然后访问http://127.0.0.1:8765。页面实时展示工具、验证失败、自修复过程和最终指标，并可下载JSON报告。

评测：收集多次报告后运行 python -m minicoder.evaluation run1.json run2.json，可得到成功率、平均步骤、平均耗时、失败验证及修复轮次汇总。

限制：目前仅支持兼容Chat Completions工具调用的模型；命令白名单偏保守；长对话尚未自动压缩，生产环境仍应增加容器隔离。
