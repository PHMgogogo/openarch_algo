# EZ Agent

EZ Agent 是一个由北航团队创建的基于大语言模型的智能代理，它能够通过 `ezcli` 工具与系统进行交互，帮助用户完成各种任务。

## 功能特性

- 🤖 基于大语言模型的智能对话代理
- 🔧 内置 `ezcli` 工具支持，可以执行系统命令和操作
- 🌐 支持 Web API 和交互式命令行两种使用方式
- 📡 支持流式输出，实时展示思考过程
- 🔄 自动工具调用结果处理，支持多轮工具调用

## 系统架构

EZ Agent 的工作流程如下：

1. **用户输入**：用户提出请求或问题
2. **LLM 推理**：大语言模型分析用户请求，决定是否需要调用工具
3. **工具调用**：如果需要工具，LLM 会以特定格式输出工具调用指令
4. **执行结果**：系统执行工具并将结果返回给 LLM
5. **最终回答**：LLM 基于工具结果给出最终回答

工具调用格式：
```xml
<ez-agent-tool>ezcli arg0 arg1 ...</ez-agent-tool>
```

## 环境要求

- Python 3.8+
- OpenAI API 兼容的大语言模型服务
- 依赖包：`openai`, `fastapi`, `uvicorn`, `python-dotenv`, `rich`

## 安装配置

1. **克隆项目**
```bash
cd algorithms/ez_agent
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
复制 `.env.template` 到 `.env` 并填写你的配置：
```bash
cp .env.template .env
```

编辑 `.env` 文件：
```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1  # 或你的API地址
OPENAI_MODEL_NAME=gpt-4  # 或你使用的模型名称
```

## 使用方法

### 命令行模式

直接运行 `main.py` 启动交互式命令行：

```bash
python main.py
```

然后你就可以和 EZ Agent 对话了。

### Web 服务模式

使用 uvicorn 启动 Web 服务：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

启动后可以：
- 访问 `http://localhost:8000` 使用网页界面
- 通过 API 接口 `POST http://localhost:8000/interact` 进行交互

### API 接口说明

**端点**：`POST /interact`

**请求体**：
```json
{
  "context": [],
  "user_input": "你的问题或请求"
}
```

**响应**：Server-Sent Events (SSE) 流式响应

## 文件说明

- `main.py` - 主程序入口，包含 CLI 和 Web API
- `PROMPT.md` - 系统提示词，定义了 EZ Agent 的行为规范
- `.algorithm.info.json` - 算法信息配置文件
- `index.html` - Web 前端页面
- `.env.template` - 环境变量模板
- `client.py` - 动态加载的 `ezcli` 客户端（运行时自动下载）

## 工作原理

EZ Agent 使用特殊的标记 `<ez-agent-tool>` 来包裹工具调用指令。当检测到这种格式时，系统会：

1. 提取命令内容
2. 执行命令（通过 `python client.py`）
3. 获取执行结果
4. 将结果替换到上下文中
5. 让 LLM 继续基于结果进行推理

整个过程可以重复多次，直到 LLM 认为已经获得足够信息可以回答用户问题。

## 注意事项

- `ezcli` 工具是 EZ Agent 专用的，用户不需要直接使用
- 工具输出会自动截断到 10240 字符以避免上下文过长
- 每次只能调用一个工具，不支持并行调用
- 需要确保网络可以连接到指定的 LLM API 服务

## 许可证

本项目属于 openarch_algo 项目的一部分，请遵循项目整体许可证。
