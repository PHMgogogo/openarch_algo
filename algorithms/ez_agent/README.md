# EZ Agent

一个基于大语言模型的智能代理，能够通过命令行工具（ezcli）自主完成用户任务，支持工具调用和流式对话。

## 概述

EZ Agent 是由北航团队开发的 AI 智能代理，核心特性：

- 🤖 基于 OpenAI 兼容 API 的大语言模型
- 🔧 支持通过 `ezcli` 工具调用 OpenArch Algo 平台的命令行接口
- 🌊 完整的流式输出支持，实时显示思考过程和工具调用
- 💻 提供 Web 聊天界面和 CLI 命令行两种交互方式
- 🔄 自动多轮工具调用，直到任务完成

## 功能特性

### 核心能力

- **工具调用**: LLM 可以自动调用 `ezcli` 命令行工具来操作 OpenArch Algo 平台
- **流式响应**: 支持 SSE 流式输出，打字机效果
- **上下文保持**: 完整维护对话上下文，支持多轮交互
- **可扩展**: 基于 FastAPI，易于集成到现有系统

### 架构

```
ez_agent/
├── main.py          # 主程序：LLM 推理循环 + FastAPI 服务
├── PROMPT.md        # 系统提示词模板
├── index.html       # Web 聊天界面
├── .env.template    # 环境变量模板
└── README.md        # 本文档
```

### 工作流程

1. 用户输入请求
2. EZ Agent 加载系统提示词 + 用户上下文
3. LLM 流式生成回复，检测工具调用
4. 如果需要调用 `ezcli`，执行命令并获取输出
5. 将工具返回结果加入上下文，让 LLM 继续生成
6. 重复直到任务完成，输出最终结果
7. 将完整对话 dump 到 `dump.md` 方便调试

## 环境变量配置

复制 `.env.template` 为 `.env` 并配置：

```env
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1  # 或你的代理地址
OPENAI_MODEL_NAME=gpt-4o  # 或其他支持工具调用的模型
```

## 依赖

```
fastapi
uvicorn
openai
python-dotenv
rich
pydantic
typing_extensions
```

这些依赖已经在项目根目录的 `requirements.txt` 中。

## 运行方式

### 1. CLI 交互模式

```bash
cd algorithms/ez_agent
python main.py
```

然后在提示符下输入你的问题，EZ Agent 会在终端中实时流式输出回复。

### 2. Web 服务模式

```bash
cd algorithms/ez_agent
uvicorn main:app --host 0.0.0.0 --port 8000
```

然后打开浏览器访问 `http://localhost:8000` 即可使用聊天界面。

## API 端点

### `GET /` 或 `/index.html`
返回 Web 聊天页面。

### `POST /interact`
与 EZ Agent 交互（SSE 流式输出）。

**请求体**:
```json
{
  "context": [],
  "user_input": "帮我查看一下当前有哪些算法实例"
}
```

- `context`: 对话上下文（可选，如果为空会自动加载系统提示词）
- `user_input`: 用户当前输入

**响应**:
Server-Sent Events 流，格式：
- 上下文更新: `data: [{"role": "system", "content": "...", ...}, ...]\n\n`
- 输出增量: `data: {"output": "当前正在生成的文本..."}\n\n`

## 在 OpenArch Algo 平台部署

EZ Agent 设计为在 OpenArch Algo 框架下运行，可以通过模板创建实例。

### 创建模板

在 `templates/` 创建 `ez_agent.json`:

```json
{
  "algorithm": {
    "id": "ez_agent",
    "version": "1.0.0",
    "description": "EZ Agent - AI 智能代理"
  },
  "entry": "uvicorn main:app --host 0.0.0.0 --port 8000",
  "restart_always": true,
  "id": "ez_agent",
  "is_temporary": false
}
```

### 添加路由规则

通过 OpenArch Gateway 添加路由规则，将 `/ezagent` 前缀路由到 EZ Agent 实例。

然后在 Web 界面的配置面板中设置 API 前缀为 `/ezagent` 即可使用。

## ezcli 工具

EZ Agent 内置了 `ezcli` 工具，这是对 OpenArch Algo 平台 `client.py` 的封装。LLM 可以通过这个工具：

- 管理算法、模板和实例
- 查询日志
- 配置路由规则
- 几乎所有平台操作

完整的 `ezcli` 文档会在运行时动态注入到系统提示词中。

## 示例对话

**用户**:
> 帮我创建一个新的 yolo_http_server 实例

**EZ Agent**:
好的，我来帮你创建一个 yolo_http_server 实例。首先让我检查一下当前有哪些模板可用。

**已调用** `ezcli process templates get`

... (工具输出) ...

找到 yolo_http_server 模板，现在创建实例：

**已调用** `ezcli process instances create --id yolo-demo yolo_http_server`

... (工具输出) ...

实例创建成功，ID 为 `yolo-demo`，状态为 RUNNING。你现在可以通过 `http://<host>:<port>/predict` 使用它了。

## 调试

对话上下文会自动保存到 `dump.md` 文件，包含:
- 每个角色（system/user/assistant/tool）的内容
- 所有工具调用和返回结果
- 完整对话历史

可以用来调试 prompt 或分析 LLM 行为。

