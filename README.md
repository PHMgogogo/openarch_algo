# OpenArch Algo

OpenArch Algo 是一个基于 FastAPI 的算法进程管理平台，允许用户动态上传、部署、管理和监控算法服务实例。

## 概述

OpenArch Algo 提供了一个完整的算法容器化运行环境，支持：

- 📦 **动态算法管理**: 上传 ZIP 包自动部署算法
- 🚀 **进程生命周期管理**: 创建模板、启动实例、停止、删除、日志查看
- 🌐 **反向代理支持**: 通过网关将请求路由到不同算法实例
- 💻 **Web 控制台**: 友好的管理界面，支持交互式操作
- 🔌 **WebSocket 终端**: 实时附加到运行进程的 stdout/stdin
- 🔄 **自动重启**: 支持崩溃自动恢复和定时重启策略

## 一键部署

只需三步即可完成完整部署：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动主服务
uvicorn asgi:app

# 3. 在另一个终端运行部署脚本，自动创建网关和 EZ Agent 实例
python deploy.py
```

部署脚本会自动：
- 检查 `algorithms/ez_agent/.env` 配置
- 删除已存在的冲突实例（如果有）
- 创建并启动网关 (`gateway`) 实例
- 创建并启动 EZ Agent (`agent`) 实例

部署完成后，访问 `http://localhost:8000/pmgr` 即可开始使用。

> **注意**: 运行 `deploy.py` 之前，请确保已复制 `algorithms/ez_agent/.env.template` 为 `.env` 并填写了你的 OpenAI API 密钥。

## 架构

```
openarch_algo/
├── asgi.py                 # FastAPI 应用入口
├── manager.py              # 进程管理器核心
├── entity.py               # 数据模型（Algorithm/Template/Instance）
├── config.py               # 配置
├── client.py               # 客户端 API 和网关服务
├── deploy.py               # 部署工具
├── console.html            # Web 终端页面
├── index.html              # 管理控制台主页
├── requirements.txt        # Python 依赖
│
├── algorithms/             # 算法仓库（预装示例）
│   ├── ez_agent/          # AI 智能代理（支持工具调用）
│   ├── openarch_gateway/  # URL 反向代理网关
│   └── yolo_http_server/  # YOLO 对象检测 HTTP 服务
│
├── framework/              # 示例机器学习框架
│   └── framework.py       # PyTorch 训练工具框架
│
├── templates/              # 预定义模板
│   ├── gateway.json
│   └── yolo_http_server.json
│
└── example/                # 示例数据
    ├── hello_world/
    └── sqrt.csv
```

## 核心概念

### 1. Algorithm（算法）
- 存储在 `algorithms/` 目录
- 每个算法包含完整代码和依赖
- 支持通过 ZIP 上传动态添加
- 包含版本和描述信息

### 2. Template（模板）
- 基于算法创建，定义运行配置
- 包含启动命令、重启策略等
- 持久化存储在 `templates/`
- 可以多次创建实例

### 3. Instance（实例）
- 从模板创建的运行进程
- 每个实例有独立的工作目录
- 独立的日志轮转和管理
- 支持 WebSocket 实时交互

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

可选依赖（用于 YOLO 示例）：
```bash
pip install torch ultralytics
```

### 2. 启动服务

```bash
uvicorn asgi:app --host 0.0.0.0 --port 8000
```

### 3. 访问管理界面

打开浏览器访问 `http://localhost:8000`

## 功能特性

### 算法管理

- **上传算法**: 通过 Web 界面上传 ZIP 包自动部署
- **浏览文件树**: 在线查看算法目录结构
- **查看文件内容**: 直接读取算法内任意文件

### 模板管理

- **创建模板**: 从已有算法配置运行参数
- **配置选项**:
  - `entry`: 启动命令（默认 `python main.py`）
  - `restart_always`: 退出自动重启
  - `restart_interval_seconds`: 重启间隔
  - `is_temporary`: 是否持久化
  - `volume`: 直接挂载算法目录（不拷贝）

### 实例管理

- **创建实例**: 从模板快速启动
- **实时状态**: 查看运行/退出状态
- **日志查看**: 在线查看 stdout/stderr
- **WebSocket 终端**: 实时交互（stdin/stdout）
- **停止/删除**: 完整生命周期管理

### URL 路由

`openarch_gateway` 算法支持三种路由匹配方式：

- **Exact**: 精确匹配完整路径
- **Prefix**: 前缀匹配，支持路径续写
- **Regex**: 正则表达式匹配

支持将请求代理到后端算法实例，也支持静态文件服务。

## API 文档

### REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/algorithms` | 列出所有算法 |
| GET | `/algorithms/{id}` | 获取算法详情 |
| POST | `/algorithms/upload` | 上传新算法 |
| POST | `/algorithms/{id}/cat` | 读取算法内文件 |
| GET | `/templates` | 列出所有模板 |
| GET | `/templates/{id}` | 获取模板详情 |
| POST | `/templates` | 创建模板 |
| GET | `/instances` | 列出所有实例 |
| GET | `/instances/{id}` | 获取实例详情 |
| POST | `/instances` | 创建并启动实例 |
| POST | `/instances/{id}/stop` | 停止实例 |
| DELETE | `/instances/{id}` | 删除实例 |
| GET | `/instances/{id}/logs/out` | 获取标准输出日志 |
| GET | `/instances/{id}/logs/err` | 获取标准错误日志 |
| WS | `/instances/{id}/attach/{wrapper}` | WebSocket 连接交互 |

### 创建模板请求示例

```json
{
  "algorithm_id": "yolo_http_server",
  "id": "yolo_http_server",
  "entry": "python main.py",
  "restart_always": true,
  "is_temporary": false,
  "volume": false,
  "restart_interval_seconds": 10
}
```

## 预装算法

### 1. [EZ Agent](algorithms/ez_agent/README.md)

基于大语言模型的智能代理，能够通过命令行工具自主完成用户任务。

**特点**:
- 支持 OpenAI 兼容 API
- 自动工具调用（ezcli）
- 流式输出
- Web 聊天界面

### 2. OpenArch Gateway

可动态配置的反向代理网关，支持将 URL 路由到后端算法实例。

**路由规则**支持:
- 精确匹配 / 前缀匹配 / 正则匹配
- 动态修改 Host
- 连接超时配置
- 静态文件服务

### 3. YOLO HTTP Server

基于 YOLOv8 的对象检测 HTTP 服务。

**端点**:
- `POST /predict`: 返回 JSON 格式检测结果
- `POST /predict/vis`: 返回带标注框的可视化图片

## 示例：部署 YOLO 检测服务

1. 在管理界面确认 `yolo_http_server` 算法已存在
2. 创建模板：
   - Algorithm ID: `yolo_http_server`
   - ID: `yolo_http_server`
   - Entry: `python main.py`
   - ✅ Restart Always
   - Interval: 10 秒
3. 点击 "Create Template"
4. 创建实例：
   - Template ID: `yolo_http_server`
   - （可选）指定实例 ID
5. 点击 "Create Instance"
6. 实例启动后，可以通过 `http://localhost:8000/yolo/predict` 访问（需要配置网关路由）

## 开发

### 目录配置

所有路径可在 `config.py` 中修改：
- `algorithm_root_path`: 算法存储根目录
- `template_root_path`: 模板存储根目录
- `instance_root_path`: 实例运行根目录
- `log_root_path`: 日志存储根目录

### 添加自定义算法

1. 在 `algorithms/your_algorithm/` 创建目录
2. 添加 `main.py` 作为入口
3. 添加 `.algorithm.info.json` 描述文件：
```json
{
  "id": "your_algorithm",
  "version": "1.0.0",
  "description": "Your algorithm description"
}
```
4. 在 Web 管理界面创建模板，然后启动实例

## 客户端工具 `ezcli`

EZ Agent 内置 `ezcli` 命令行工具，封装了完整的平台 API，可以让 LLM 自主管理平台资源。

支持的命令包括：
- 列出/获取算法、模板、实例
- 创建模板和实例
- 停止/删除实例
- 查看日志
- 管理网关路由规则

## 许可证

MIT
