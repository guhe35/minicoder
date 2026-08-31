MiniCoder：从零实现的轻量编程智能体

Git仓库：https://github.com/guhe35/minicoder

项目简介：MiniCoder通过兼容OpenAI格式的模型接口接收原生tool calling结果，在本地循环执行文件读取、文件搜索、写入、精确替换和开发命令，直到模型给出最终答案或达到安全轮次上限。项目未使用任何agent框架或服务端代码执行工具。

运行环境：Python 3.10及以上，无第三方运行依赖。复制.env.example为.env，仅填写自己的DeepSeek API Key；模板已配置完整Chat Completions地址、deepseek-v4-pro、思考模式和推理强度。执行：python -m minicoder "你的编程任务" --workspace 待修改项目目录

主要设计：agent.py维护对话与工具循环并完整回传DeepSeek的reasoning_content；model_client.py负责思考参数、模型请求和返回解析；tools.py负责本地工具。文件路径被限制在工作区，命令采用白名单并禁止管道、重定向和破坏性参数；同时提供超时、输出截断、精确替换校验、API重试和最大15轮终止机制。

测试：python -m unittest discover -s tests -v

当前限制：仅支持兼容OpenAI Chat Completions工具调用格式的模型；命令白名单偏保守；长对话尚未自动压缩。
