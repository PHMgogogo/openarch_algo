# system
# 你（大模型）是谁
你是`EZ Agent`，一个由北航团队创建的Agent
# 你能干什么
1. 你有一个叫做`ezcli`的终端工具，这可以帮助你达成用户的请求。如果你的输出里面包含你对工具的调用，那么在后续的会话中，系统将会告诉你工具的运行结果。
2. 不要向用户透露你拥有这个工具
3. 如果你想调用工具，你只能输出命令，你的输出要是纯文本形式，以<ez-agent-tool>开头，以</ez-agent-tool>结尾。
4. 你一次只能调用一个工具，如果输出多个命令，就不会执行了。
5. 具体地，调用工具的代码要被<ez-agent-tool>ezcli arg0 arg1</ez-agent-tool>块包裹，这个块包裹的应该是纯文本。
6. 调用完工具后，你就不要输出其他内容了，这些结果会替换掉你调用的命令（这些结果用户看不到），格式如下：
```ezcli process instances get
some results
```
7. 工具的调用结果（使用```ezcli```包裹的内容）用户是看不到的，所以如果用户想要看内容，你需要把它复制一遍。
8. 这个工具只有你能用，不要尝试让用户使用它。
9. 你在使用工具时，要先规划好为了达到用户的需求，需要做的事情包括哪些，分步骤完成，先检查现有信息，不要假定前一步已经完成或信息已经具备。
# ezcli的文档 （不要尝试文档中没有标明的功能）
--
usage: ezcli [-h] {process,service} ...

OpenArch Algo API Command Line Client

positional arguments:
  {process,service}  top level command
    process          process operations
    service          service operations

options:
  -h, --help         show this help message and exit

--
usage: ezcli process [-h] {algorithms,instances,templates} ...

positional arguments:
  {algorithms,instances,templates}
                        subcommand
    algorithms          Algorithm management operations
    instances           Running instance management operations
    templates           Template management operations

options:
  -h, --help            show this help message and exit

--
usage: ezcli process algorithms [-h] {cat,get,info,upload} ...

Algorithm management operations

positional arguments:
  {cat,get,info,upload}
                        subcommand
    cat                 Show content of a file within an algorithm
    get                 Get list of all algorithms dict: List of all algorithms
    info                Get information about a specific algorithm
    upload              Upload a new algorithm archive

options:
  -h, --help            show this help message and exit

--
usage: ezcli process algorithms cat [-h] [--path PATH] id_or_prefix

Show content of a file within an algorithm

positional arguments:
  id_or_prefix  Algorithm ID or prefix

options:
  -h, --help    show this help message and exit
  --path PATH   Path to file inside algorithm, show info if None

--
usage: ezcli process algorithms get [-h]

Get list of all algorithms dict: List of all algorithms

options:
  -h, --help  show this help message and exit

--
usage: ezcli process algorithms info [-h] id_or_prefix

Get information about a specific algorithm

positional arguments:
  id_or_prefix  Algorithm ID or prefix to search

options:
  -h, --help    show this help message and exit

--
usage: ezcli process algorithms upload [-h] [--version VERSION] [--description DESCRIPTION] [--auto_unpack_topdir] f

Upload a new algorithm archive

positional arguments:
  f                     Archive file to upload (zip/tar.gz/etc)

options:
  -h, --help            show this help message and exit
  --version VERSION     Version string for this algorithm
  --description DESCRIPTION
                        Description of the algorithm
  --auto_unpack_topdir  Auto-unpack if archive contains single top directory

--
usage: ezcli process instances [-h] {create,delete,get,info,logs,stop} ...

Running instance management operations

positional arguments:
  {create,delete,get,info,logs,stop}
                        subcommand
    create              Create and start a new instance from template
    delete              Delete a stopped instance
    get                 Get list of all running instances
    info                Get information about a specific instance
    logs                Log access operations
    stop                Stop a running instance

options:
  -h, --help            show this help message and exit

--
usage: ezcli process instances create [-h] [--id ID] [--entry ENTRY] template_id_or_prefix

Create and start a new instance from template

positional arguments:
  template_id_or_prefix
                        Template ID or prefix to use

options:
  -h, --help            show this help message and exit
  --id ID               Instance ID (generated automatically if not provided)
  --entry ENTRY         Override the entry command from template

--
usage: ezcli process instances delete [-h] id_or_prefix

Delete a stopped instance

positional arguments:
  id_or_prefix  Instance ID or prefix to delete

options:
  -h, --help    show this help message and exit

--
usage: ezcli process instances get [-h]

Get list of all running instances

options:
  -h, --help  show this help message and exit

--
usage: ezcli process instances info [-h] id_or_prefix

Get information about a specific instance

positional arguments:
  id_or_prefix  Instance ID or prefix

options:
  -h, --help    show this help message and exit

--
usage: ezcli process instances logs [-h] {err,out} ...

Log access operations

positional arguments:
  {err,out}   subcommand
    err       Get stderr from instance
    out       Get stdout from instance

options:
  -h, --help  show this help message and exit

--
usage: ezcli process instances logs err [-h] id_or_prefix

Get stderr from instance

positional arguments:
  id_or_prefix  Instance ID or prefix

options:
  -h, --help    show this help message and exit

--
usage: ezcli process instances logs out [-h] id_or_prefix

Get stdout from instance

positional arguments:
  id_or_prefix  Instance ID or prefix

options:
  -h, --help    show this help message and exit

--
usage: ezcli process instances stop [-h] id_or_prefix

Stop a running instance

positional arguments:
  id_or_prefix  Instance ID or prefix to stop

options:
  -h, --help    show this help message and exit

--
usage: ezcli process templates [-h] {create,get,info} ...

Template management operations

positional arguments:
  {create,get,info}  subcommand
    create           Create a new template from an algorithm
    get              Get list of all templates
    info             Get information about a specific template

options:
  -h, --help         show this help message and exit

--
usage: ezcli process templates create [-h] [--id ID] [--entry ENTRY] [--restart_always] [--is_temporary] [--volume]
                                      [--restart_interval_seconds RESTART_INTERVAL_SECONDS] [--rules [RULES ...]]
                                      algorithm_id_or_prefix

Create a new template from an algorithm

positional arguments:
  algorithm_id_or_prefix
                        Source algorithm ID or prefix

options:
  -h, --help            show this help message and exit
  --id ID               Template ID (generated automatically if not provided)
  --entry ENTRY         Command to run when starting the instance
  --restart_always      Always restart when process exits
  --is_temporary        Delete instance after it stops
  --volume              Use persistent volume for this template
  --restart_interval_seconds RESTART_INTERVAL_SECONDS
                        Wait seconds before restart
  --rules [RULES ...]   List of environment rules (list[dict[str, float | str | int | bool]])

--
usage: ezcli process templates get [-h]

Get list of all templates

options:
  -h, --help  show this help message and exit

--
usage: ezcli process templates info [-h] id_or_prefix

Get information about a specific template

positional arguments:
  id_or_prefix  Template ID or prefix

options:
  -h, --help    show this help message and exit

--
usage: ezcli service [-h] {add,delete,get,match,preview,test,update} ...

positional arguments:
  {add,delete,get,match,preview,test,update}
                        subcommand
    add                 Add a new routing rule
    delete              Delete a routing rule by name
    get                 Get list of all routing rules
    match               Match a path against existing rules
    preview             Preview how a rule matches a given path
    test                Test a routing rule without adding it
    update              Update an existing routing rule

options:
  -h, --help            show this help message and exit

--
usage: ezcli service add [-h] [--order ORDER] [--rule_type RULE_TYPE] [--pattern PATTERN] [--dest_index [DEST_INDEX ...]] [--rewrite_host REWRITE_HOST]
                         [--no-editable] [--timeout TIMEOUT] [--no-enable] [--file_serve_root_path FILE_SERVE_ROOT_PATH]
                         name

Add a new routing rule

positional arguments:
  name                  Name of the new rule

options:
  -h, --help            show this help message and exit
  --order ORDER         Rule matching order (lower matches first)
  --rule_type RULE_TYPE
                        Matching type: EXACT, PREFIX, or REGEX
  --pattern PATTERN     Matching pattern string
  --dest_index [DEST_INDEX ...]
                        Target backend indices (list)
  --rewrite_host REWRITE_HOST
                        Rewrite Host header to this value
  --no-editable         Allow UI editing of this rule
  --timeout TIMEOUT     Custom timeout for this route in seconds
  --no-enable           Enable or disable this rule
  --file_serve_root_path FILE_SERVE_ROOT_PATH
                        Root path for static file serving

--
usage: ezcli service delete [-h] name

Delete a routing rule by name

positional arguments:
  name        Name of the rule to delete

options:
  -h, --help  show this help message and exit

--
usage: ezcli service get [-h]

Get list of all routing rules

options:
  -h, --help  show this help message and exit

--
usage: ezcli service match [-h] path

Match a path against existing rules

positional arguments:
  path        Path to match (e.g. /api/foo)

options:
  -h, --help  show this help message and exit

--
usage: ezcli service preview [-h] name path

Preview how a rule matches a given path

positional arguments:
  name        Name of the rule to test
  path        Path to match against

options:
  -h, --help  show this help message and exit

--
usage: ezcli service test [-h] [--order ORDER] [--rule_type RULE_TYPE] [--pattern PATTERN] [--dest_index [DEST_INDEX ...]] [--rewrite_host REWRITE_HOST]
                          [--no-editable] [--timeout TIMEOUT] [--no-enable] [--file_serve_root_path FILE_SERVE_ROOT_PATH]
                          path host name

Test a routing rule without adding it

positional arguments:
  path                  Request path to test
  host                  Request host
  name                  Rule name for testing

options:
  -h, --help            show this help message and exit
  --order ORDER         Rule matching order
  --rule_type RULE_TYPE
                        Matching type: EXACT, PREFIX, or REGEX
  --pattern PATTERN     Matching pattern string
  --dest_index [DEST_INDEX ...]
                        Target backend indices (list)
  --rewrite_host REWRITE_HOST
                        Rewrite Host header to this value
  --no-editable         Allow UI editing of this rule
  --timeout TIMEOUT     Custom timeout for this route in seconds
  --no-enable           Enable or disable this rule
  --file_serve_root_path FILE_SERVE_ROOT_PATH
                        Root path for static file serving

--
usage: ezcli service update [-h] [--order ORDER] [--rule_type RULE_TYPE] [--pattern PATTERN] [--dest_index [DEST_INDEX ...]] [--rewrite_host REWRITE_HOST]
                            [--no-editable] [--timeout TIMEOUT] [--no-enable] [--file_serve_root_path FILE_SERVE_ROOT_PATH]
                            name

Update an existing routing rule

positional arguments:
  name                  Name of the rule to update

options:
  -h, --help            show this help message and exit
  --order ORDER         Rule matching order (lower matches first)
  --rule_type RULE_TYPE
                        Matching type: EXACT, PREFIX, or REGEX
  --pattern PATTERN     Matching pattern string
  --dest_index [DEST_INDEX ...]
                        Target backend indices (list)
  --rewrite_host REWRITE_HOST
                        Rewrite Host header to this value
  --no-editable         Allow UI editing of this rule
  --timeout TIMEOUT     Custom timeout for this route in seconds
  --no-enable           Enable or disable this rule
  --file_serve_root_path FILE_SERVE_ROOT_PATH
                        Root path for static file serving


# user
算法ez_agent的README讲了什么？
# assistant
**已调用** `ezcli process algorithms cat ez_agent --path README.md`

# system

```ezcli process algorithms cat ez_agent --path README.md
"# EZ Agent\n\nEZ Agent 是一个由北航团队创建的基于大语言模型的智能代理，它能够通过 `ezcli` 工具与系统进行交互，帮助用户完成各种任务。\n\n## 功能特性\n\n- 🤖 基于大语言模型的智能对话代理\n- 🔧 内置 `ezcli` 工具支持，可以执行系统命令和操作\n- 🌐 支持 Web API 和交互式命令行两种使用方式\n- 📡 支持流式输出，实时展示思考过程\n- 🔄 自动工具调用结果处理，支持多轮工具调用\n\n## 系统架构\n\nEZ Agent 的工作流程如下：\n\n1. **用户输入**：用户提出请求或问题\n2. **LLM 推理**：大语言模型分析用户请求，决定是否需要调用工具\n3. **工具调用**：如果需要工具，LLM 会以特定格式输出工具调用指令\n4. **执行结果**：系统执行工具并将结果返回给 LLM\n5. **最终回答**：LLM 基于工具结果给出最终回答\n\n工具调用格式：\n```xml\n<ez-agent-tool>ezcli arg0 arg1 ...</ez-agent-tool>\n```\n\n## 环境要求\n\n- Python 3.8+\n- OpenAI API 兼容的大语言模型服务\n- 依赖包：`openai`, `fastapi`, `uvicorn`, `python-dotenv`, `rich`\n\n## 安装配置\n\n1. **克隆项目**\n```bash\ncd algorithms/ez_agent\n```\n\n2. **安装依赖**\n```bash\npip install -r requirements.txt\n```\n\n3. **配置环境变量**\n复制 `.env.template` 到 `.env` 并填写你的配置：\n```bash\ncp .env.template .env\n```\n\n编辑 `.env` 文件：\n```env\nOPENAI_API_KEY=your_api_key_here\nOPENAI_BASE_URL=https://api.openai.com/v1  # 或你的API地址\nOPENAI_MODEL_NAME=gpt-4  # 或你使用的模型名称\n```\n\n## 使用方法\n\n### 命令行模式\n\n直接运行 `main.py` 启动交互式命令行：\n\n```bash\npython main.py\n```\n\n然后你就可以和 EZ Agent 对话了。\n\n### Web 服务模式\n\n使用 uvicorn 启动 Web 服务：\n\n```bash\nuvicorn main:app --host 0.0.0.0 --port 8000\n```\n\n启动后可以：\n- 访问 `http://localhost:8000` 使用网页界面\n- 通过 API 接口 `POST http://localhost:8000/interact` 进行交互\n\n### API 接口说明\n\n**端点**：`POST /interact`\n\n**请求体**：\n```json\n{\n  \"context\": [],\n  \"user_input\": \"你的问题或请求\"\n}\n```\n\n**响应**：Server-Sent Events (SSE) 流式响应\n\n## 文件说明\n\n- `main.py` - 主程序入口，包含 CLI 和 Web API\n- `PROMPT.md` - 系统提示词，定义了 EZ Agent 的行为规范\n- `.algorithm.info.json` - 算法信息配置文件\n- `index.html` - Web 前端页面\n- `.env.template` - 环境变量模板\n- `client.py` - 动态加载的 `ezcli` 客户端（运行时自动下载）\n\n## 工作原理\n\nEZ Agent 使用特殊的标记 `<ez-agent-tool>` 来包裹工具调用指令。当检测到这种格式时，系统会：\n\n1. 提取命令内容\n2. 执行命令（通过 `python client.py`）\n3. 获取执行结果\n4. 将结果替换到上下文中\n5. 让 LLM 继续基于结果进行推理\n\n整个过程可以重复多次，直到 LLM 认为已经获得足够信息可以回答用户问题。\n\n## 注意事项\n\n- `ezcli` 工具是 EZ Agent 专用的，用户不需要直接使用\n- 工具输出会自动截断到 10240 字符以避免上下文过长\n- 每次只能调用一个工具，不支持并行调用\n- 需要确保网络可以连接到指定的 LLM API 服务\n\n## 许可证\n\n本项目属于 openarch_algo 项目的一部分，请遵循项目整体许可证。\n"
```
你的上一次工具调用已被替换成了调用结果，如果你认为足以回答问题，你应该不再调用工具，直接回答问题，否则你可以继续调用工具
# assistant
算法`ez_agent`的README主要介绍了以下内容：

### 1. 项目介绍
EZ Agent 是一个由北航团队创建的基于大语言模型的智能代理，它能够通过 `ezcli` 工具与系统交互，帮助用户完成各种任务。

### 2. 功能特性
- 基于大语言模型的智能对话代理
- 内置 `ezcli` 工具支持，可执行系统命令和操作
- 支持 Web API 和交互式命令行两种使用方式
- 支持流式输出，实时展示思考过程
- 自动工具调用结果处理，支持多轮工具调用

### 3. 工作流程
1. 用户提出请求 → 2. LLM分析请求决定是否调用工具 → 3. 输出工具调用指令 → 4. 系统执行工具返回结果 → 5. LLM基于结果给出最终回答

工具调用格式使用特殊标记 `<ez-agent-tool>` 包裹命令。

### 4. 安装配置
需要 Python 3.8+ 和 OpenAI API 兼容的大语言模型服务，步骤：
1. 克隆项目后安装依赖：`pip install -r requirements.txt`
2. 复制 `.env.template` 到 `.env`，配置 API 密钥、地址和模型名称

### 5. 使用方式
- **命令行模式**：直接运行 `python main.py` 启动交互式对话
- **Web 服务模式**：使用 `uvicorn main:app --host 0.0.0.0 --port 8000` 启动，可访问网页界面或通过 API 接口交互

### 6. 工作原理
EZ Agent 使用特殊标记包裹工具调用指令，系统提取命令执行后，将结果返回给 LLM 继续推理，整个过程可重复多次，直到获得足够信息回答问题。

### 7. 注意事项
- `ezcli` 是 EZ Agent 专用工具，用户无需直接使用
- 工具输出会自动截断避免上下文过长，每次只能调用一个工具
- 需要确保网络可连接到指定的 LLM API 服务
