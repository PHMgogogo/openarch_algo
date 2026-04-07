# OpenArch Algo

一个算法管理和执行平台，包含专门的YOLO HTTP对象检测服务器。

## 项目概述

该系统提供：
- 管理和执行隔离算法实例的框架
- 基于进程的算法执行与实时监控
- 基于FastAPI的YOLO对象检测HTTP服务器
- 基于模板的配置系统

## 架构

### 核心组件

1. **config.py** - 集中配置
   - 日志路径和轮转设置（最大文件：10MB，缓冲区：64KB）
   - 实例/数据/模板/算法目录
   - Python命令和模板路径

2. **entity.py** - 数据模型（基于Pydantic）
   - `Algorithm`: 表示带有ID、版本、描述的算法；管理文件存储和树结构
   - `Template`: 定义执行参数（入口命令、重启行为、算法引用）
   - `Instance`: 模板的运行实例，带有状态跟踪（NOT_READY, STOP, RUNNING, EXITED）
   - `Log`: 带自动文件轮转的缓冲日志系统

3. **manager.py** - 进程管理器
   - `ProcessManager`: 管理算法生命周期
     - `__init__()`: 加载 `instances/` 目录下已有实例配置
     - `create_instance()`: 注册新实例并准备日志目录
     - `run()`: 从模板创建实例、准备运行目录并启动
     - `exec()`: 在实例工作目录中生成子进程，环境变量包含 `PYTHONUNBUFFERED=1`
     - `watch()`: 非阻塞读取子进程 `stdout` / `stderr`，写入缓冲日志；检测进程退出并更新状态
     - `watch_loop()`: 以指定间隔循环调用 `watch()`
     - `get_log_out()` / `get_log_err()`: 读取实例输出或错误日志内容
     - `get_template()`: 支持按模板ID前缀查找并加载模板JSON
     - `get_algorithm()`: 支持按算法ID前缀查找并加载算法定义，若不存在则自动创建元信息文件
     - `upload_unzip_algorithm()`: 将 ZIP 包解压到算法目录并持久化算法元信息
   - `Template` 和 `Instance` 运行流程
     - 实例创建后，`get_ready()` 会将算法文件复制到 `instances/<id>/` 工作目录
     - 运行时实例状态在 `InstanceStatus` 中跟踪：`NOT_READY`, `STOP`, `RUNNING`, `EXITED`

4. **algorithms/yolo_http_server/main.py** - FastAPI HTTP检测服务器
   - **POST `/predict`**: 返回包含检测框、分数、类别ID和名称的JSON
   - **POST `/predict/vis`**: 返回带边界框和标签的注释图像（PNG）
   - 使用YOLOv8 nano模型（`yolo26n.pt`）
   - 默认推理尺寸：640px

## 依赖

```
torch              - PyTorch深度学习
fastapi            - HTTP API框架
ultralytics        - YOLO模型库
Pillow             - 图像处理
numpy              - 数组操作
pydantic           - 数据验证
```

## 如何运行YOLO HTTP服务器

### 1. 安装
```bash
pip install -r requirements.txt
```

### 2. 自动启动（通过ProcessManager）
```python
import asyncio
from manager import ProcessManager

async def main():
    pm = ProcessManager()
    template = pm.get_template("yolo_http_server")
    instance_id = await pm.run(template)
    await pm.watch_loop()  # 后台监控

asyncio.run(main())
```

### 3. 手动启动
```bash
cd algorithms/yolo_http_server
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. API使用

**对象检测（JSON）**:
```bash
curl -X POST "http://localhost:8000/predict" \
  -F "file=@image.jpg"
```

响应:
```json
{
  "predictions": [
    {
      "box": [x1, y1, x2, y2],
      "score": 0.95,
      "class_id": 0,
      "class_name": "person"
    }
  ]
}
```

**可视化（注释图像）**:
```bash
curl -X POST "http://localhost:8000/predict/vis" \
  -F "file=@image.jpg" -o result.png
```

## 配置系统

### 模板配置（templates/yolo_http_server.json）
```json
{
  "algorithm": {
    "id": "yolo_http_server",
    "version": "1.0.0",
    "description": "YOLO HTTP SERVER"
  },
  "entry": "uvicorn main:app --host 0.0.0.0 --port 8000",
  "restart_always": true,
  "id": "yolo_http_server",
  "is_temporary": false
}
```

### 关键配置选项（config.py）
| 选项 | 目的 |
|------|------|
| `log_root_path` | 所有日志的基础目录 |
| `log_buffer_size` | 64KB - 超过时刷新日志到磁盘 |
| `log_max_file_size` | 10MB - 超过大小时轮转日志 |
| `instance_root_path` | 运行时实例工作目录 |
| `template_root_path` | 保存的执行模板 |
| `algorithm_root_path` | 算法包/可执行文件 |

## 文件结构

```
openarch_algo/
├── config.py                          # 配置
├── entity.py                          # 数据模型
├── manager.py                         # ProcessManager
├── data.py                            # 数据类
├── requirements.txt                   # 依赖
├── algorithms/
│   ├── yolo_http_server/
│   │   ├── main.py                   # FastAPI服务器
│   │   └── yolo26n.pt                # YOLO模型权重
│   └── test/
│       └── main.py                   # 测试脚本
├── templates/
│   └── yolo_http_server.json         # 服务器模板配置
└── framework/                         # （预留供将来使用）
```

## 关键特性

✅ **隔离进程执行**: 每个算法在其自己的子进程中运行  
✅ **自动重启**: 可配置的进程失败重启  
✅ **实时监控**: 带缓冲日志的异步进程监视  
✅ **对象检测**: 通过HTTP API的YOLOv8-nano  
✅ **灵活部署**: 基于模板的实例创建  
✅ **基于ZIP的更新**: 将算法包作为ZIP文件上传  
✅ **可扩展日志**: 带自动轮转的缓冲日志  

该架构支持并发部署多个算法，具有隔离的执行上下文和集中管理。