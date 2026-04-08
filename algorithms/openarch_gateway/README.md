# OpenArch Gateway

OpenArch Gateway 是一个基于 FastAPI 的高性能反向代理网关服务，支持灵活的路由规则配置和管理。它能够根据预定义的规则将请求代理到不同的后端服务，支持 HTTP 和 WebSocket 协议。

## TODO


## 功能特性

- **灵活的路由规则**: 支持精确匹配、前缀匹配和正则表达式匹配
- **动态规则管理**: 通过 REST API 动态添加、修改、删除和查询代理规则
- **WebSocket 支持**: 完整支持 WebSocket 协议的代理转发
- **高性能**: 基于异步 I/O，支持高并发请求处理
- **配置热重载**: 支持规则配置的热重载，无需重启服务
- **安全防护**: 防止代理循环和无效请求
- **可扩展**: 插件化的规则引擎，易于扩展新的匹配逻辑

## 安装

### 环境要求

- Python 3.8+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖包：
- fastapi: Web 框架
- fastapi-reverse-proxy: 反向代理中间件
- pydantic: 数据验证
- uvicorn: ASGI 服务器
- filelock: 文件锁
- aiohttp: 异步 HTTP 客户端（测试用）

## 快速开始

### 启动服务

```bash
python main.py
```

服务将在 `http://127.0.0.1:8000` 启动。

### 默认路由

- `/docs`: FastAPI 自动生成的 API 文档
- `/pmgr/*`: 代理管理 API（如果启用）
- `/pmgr/index.html`: Web 管理界面（如果启用代理管理功能）

## 配置

### 环境变量

- `PROXY_RULE_PATH`: 规则配置文件路径（默认: `./rules.json`）
- `PROXY_LOCK_PATH`: 规则文件锁路径（默认: `./rules.json.lock`）
- `EXPOSE_PROXY_MANAGER`: 是否暴露代理管理 API（默认: `true`）
- `PROXY_MANAGER_API`: 代理管理 API 前缀（默认: `/pmgr`）

### 规则配置

规则配置文件为 JSON 格式，包含规则数组。每个规则包含以下字段：

- `name`: 规则名称（唯一标识符）
- `order`: 匹配优先级（数字越大优先级越高）
- `rule_type`: 匹配类型
  - `1`: 精确匹配 (EXACT)
  - `2`: 前缀匹配 (PREFIX)
  - `3`: 正则匹配 (REGEX)
- `pattern`: 匹配模式
- `dest_index`: 目标 URL 构造索引
- `dest_format`: 目标 URL 格式字符串
- `rewrite_host`: 重写主机头（可选）
- `editable`: 是否可编辑（默认: true）
- `timeout`: 超时时间（秒，可选）
- `enable`: 是否启用（默认: true）

#### 示例配置

```json
[
    {
        "name": "api_proxy",
        "order": 10,
        "rule_type": "2",
        "pattern": "/api",
        "dest_index": [1],
        "dest_format": "http://backend-service%s",
        "rewrite_host": "backend-service.com",
        "editable": true,
        "timeout": 30.0,
        "enable": true
    }
]
```

## API 文档

### 代理管理 API

如果启用了代理管理功能，可以通过以下 API 管理规则：

#### 获取所有规则
```
GET /pmgr/rules
```

#### 添加新规则
```
POST /pmgr/rules
Content-Type: application/json

{
    "name": "new_rule",
    "pattern": "/new",
    "dest_format": "http://new-service%s"
}
```

#### 更新规则
```
PUT /pmgr/rules
Content-Type: application/json

{
    "name": "existing_rule",
    "pattern": "/updated",
    "dest_format": "http://updated-service%s"
}
```

#### 删除规则
```
DELETE /pmgr/rules/{rule_name}
```

#### 规则匹配测试
```
POST /pmgr/rules/match
Content-Type: application/json

{
    "path": "/test/path"
}
```

#### 规则预览
```
POST /pmgr/rules/{rule_name}/preview
Content-Type: application/json

"path": "/test/path"
```

## Web 管理界面

OpenArch Gateway 提供了基于 Web 的图形化管理界面，方便用户可视化管理代理规则。

### 访问管理界面

启动服务后，访问 `http://127.0.0.1:8000/pmgr/index.html` 即可打开管理界面。

### 功能特性

- **规则列表**: 以表格形式显示所有代理规则，支持排序和状态查看
- **添加规则**: 通过表单快速添加新的代理规则
- **编辑规则**: 实时编辑现有规则的所有属性
- **删除规则**: 删除不需要的代理规则
- **实时预览**: 输入路径后实时显示匹配的规则和转发目标
- **状态管理**: 启用/禁用规则，查看规则优先级

### 界面说明

- **规则表格**: 显示规则名称、优先级、匹配类型、模式、目标格式等信息
- **操作按钮**: 每个可编辑规则都有编辑和删除按钮
- **预览区域**: 实时输入路径预览匹配结果
- **模态框表单**: 用于添加和编辑规则的弹出表单

## 测试

项目包含性能测试脚本 `test.py`，用于测试代理的吞吐量。

### 运行测试

```bash
python test.py
```

测试将分别对命中和未命中的请求进行性能测试，输出 QPS（每秒查询数）。

### 测试参数

- `TOTAL_REQUESTS`: 总请求数（默认: 20000）
- `CONCURRENCY`: 并发数（默认: 200）
- `BASE_URL`: 测试基础 URL（默认: "http://127.0.0.1:8000"）

### 性能测试结果

以下表格展示了不同并发数（Workers）下的 QPS 性能测试结果。测试基于总共 20000 个请求，使用不同的并发连接数进行测试。

| Workers | 命中 QPS | 未命中 QPS |
| ------- | -------- | ---------- |
| 1       | 3497.62  | 3926.59    |
| 2       | 7020.93  | 8019.98    |
| 4       | 10546.99 | 12396.33   |
| 8       | 13693.97 | 15238.00   |
| 16      | 13909.05 | 14974.58   |

**注**: 
- 命中 QPS: 请求匹配到代理规则并成功转发的 QPS
- 未命中 QPS: 请求未匹配到规则返回 404 的 QPS
- 实际性能可能因硬件配置、网络环境和后端服务响应时间而异
- 建议在生产环境中进行实际测试以获取准确的性能数据

## 架构说明

### 核心组件

1. **ProxyManager**: 规则管理器，负责规则的加载、保存和匹配
2. **UrlProxyRule**: 代理规则模型，定义匹配逻辑和目标构造
3. **FastAPI 应用**: 提供 HTTP/WebSocket 代理和管理系统 API

### 工作流程

1. 客户端请求到达网关
2. ProxyManager 根据请求路径匹配规则
3. 如果匹配成功，构造目标 URL 并转发请求
4. 如果匹配失败，返回 404 错误

### 安全考虑

- 防止代理循环：检查目标主机是否与原始主机相同
- 文件锁：确保规则文件的并发安全访问
- 输入验证：使用 Pydantic 进行数据验证

## 开发

### 项目结构

```
openarch_gateway/
├── main.py          # 主应用文件
├── rules.json       # 规则配置文件
├── test.py          # 性能测试脚本
├── README.md        # 项目文档
└── __pycache__/     # Python 缓存文件
```

### 扩展开发

要添加新的匹配类型：

1. 在 `RuleType` 枚举中添加新类型
2. 在 `UrlProxyRule` 类中实现对应的匹配方法
3. 更新 `model_post_init` 方法的默认值设置

## 许可证

[请根据项目实际情况填写许可证信息]

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

[请根据项目实际情况填写联系信息]