from pydantic import BaseModel, Field
from jsonpatch import apply_patch
from typing import Literal, Any, Annotated
from agents import function_tool, RunContextWrapper
from agent import AgentContext
from base import Pipeline, source, get_all_node_cls


class AddPatch(BaseModel):
    op: Literal["add"]
    path: str
    value: Any


class RemovePatch(BaseModel):
    op: Literal["remove"]
    path: str


class ReplacePatch(BaseModel):
    op: Literal["replace"]
    path: str
    value: Any


class MovePatch(BaseModel):
    op: Literal["move"]
    path: str
    from_: str = Field(alias="from")


class CopyPatch(BaseModel):
    op: Literal["copy"]
    path: str
    from_: str = Field(alias="from")


class TestPatch(BaseModel):
    op: Literal["test"]
    path: str
    value: Any


Patch = Annotated[
    AddPatch | RemovePatch | ReplacePatch | MovePatch | CopyPatch | TestPatch,
    Field(discriminator="op"),
]


class PipelineAgentContext(AgentContext):
    value: Pipeline


@function_tool
def patch(rcw: RunContextWrapper[PipelineAgentContext], patches: list[Patch]) -> str:
    """
    Edit the pipeline with RFC 6902 patchs.
    """
    rcw.context.value = Pipeline.model_validate(
        apply_patch(
            rcw.context.value.model_dump(by_alias=True),
            patch=[
                p.model_dump(
                    by_alias=True,
                    exclude_none=False,
                )
                for p in patches
            ],
            in_place=True,
        ),
        by_alias=True,
    )
    rcw.context.changed = True
    return "ok"


@function_tool
def view(rcw: RunContextWrapper[PipelineAgentContext]) -> str:
    """
    View current pipeline content.
    """
    return rcw.context.value.model_dump_json(
        by_alias=True, ensure_ascii=False, indent=4
    )


@function_tool
def format(rcw: RunContextWrapper[PipelineAgentContext]) -> str:
    """
    Format the pipeline, which should be called after all edits.
    """
    rcw.context.value.update_prev_next()
    rcw.context.value.update_order()
    rcw.context.value.update_xy(300, 100)
    rcw.context.changed = True
    return True


def get_instructions():
    node_list = "\n".join(
        f"- `{cls.__name__}`（分类：{cls.model_fields['category'].default if 'category' in cls.model_fields else ''}）"
        for cls in get_all_node_cls()
    )
    return f"""你是 OpenArch Pipeline 开发助手，负责通过对话创建、修改和调试数据流水线（Pipeline）。你会使用提供的工具直接编辑流水线 JSON，并最终交给用户确认。

# 一、什么是 Pipeline

Pipeline 是一张有向无环图（DAG），由若干节点（Node）构成。其 JSON 结构为：

- `name` / `id`：流水线名称与唯一标识（id 只允许字母、数字、`_`、`-`）。
- `nodes`：字典，键为节点 id，值为节点对象。
- `cron_expr` / `cron_enable`：定时执行配置，一般不用修改。
- `return_data` / `return_state`：运行后需要返回的数据列名 / 状态键名，可选。

节点之间通过两种方式协作：

1. **连接关系**：`prev`（前驱节点 id 列表）与 `next`（后继节点 id 列表）。二者互为镜像，构成 DAG 的边。
2. **数据与状态**：
   - 数据流：上游节点把结果写入 `write_data` 命名的数据列，下游节点通过 `read_data` 读取这些列。
   - 状态：节点通过 `out_parameters` 声明输出写入的 state 键，通过 `in_parameters` 里的 ValueRef 读取 state 值（如回归系数 k、b，相关系数 rho 等标量）。

# 二、节点字段约定

- `id`：节点唯一标识，必须满足 `^[A-Za-z0-9_-]+$`，且全图唯一。
- `node_type`：必须是下方已注册的节点类型之一，不可自创。
- `title`：可选，节点的显示名称。
- `in_parameters`：节点输入参数对象，字段必须符合该节点类型的 InParameters 定义（见下方源码）。
- `category`：节点分类（INPUT / OUTPUT / BY_ROW / BY_COLUMN / ALARM / STATE / REGRESSION / REMOTE），由系统自动确定，不要手动修改。
- `x` / `y` / `order`：布局与执行顺序，由 `format` 工具自动计算，不要手动设置。
- `read_data` / `write_data`：数据列名；`out_parameters`：本节点输出写入的 state 键名。

# 三、工具使用方式

1. `view`：查看当前 Pipeline 完整 JSON。**每次修改前先 view，确保基于最新内容做 patch。**
2. `patch`：使用 RFC 6902 JSON Patch 编辑 Pipeline。常见操作：
   - 新增节点：`{{"op": "add", "path": "/nodes/{{节点id}}", "value": {{节点对象}}}}`
   - 修改字段：`{{"op": "replace", "path": "/nodes/{{节点id}}/{{字段}}", "value": ...}}`
   - 删除节点：`{{"op": "remove", "path": "/nodes/{{节点id}}"}}`（同时清理其他节点对它的引用）
   - 修改数组：`{{"op": "add", "path": "/nodes/{{id}}/read_data/0", "value": ...}}` 或 `{{"op": "replace", "path": "/nodes/{{id}}/read_data", "value": [...]}}`
   - 一次可传入多个 patch，按顺序应用。
3. `format`：所有编辑完成后调用一次，自动修复 `prev` / `next` 双向一致性，并重新计算 `order`、`x`、`y`。

# 四、推荐开发流程

1. `view` 查看当前流水线。
2. 在脑中规划需要增删改的节点与连接，设计好数据列名 / 状态键名。
3. 用 `patch` 逐项修改（尽量一次提交多个 patch）。
4. 用 `view` 检查结果，确认节点字段、连接、参数正确；如有问题继续 `patch`。
5. 全部完成后调用 `format`，再 `view` 一次确认最终结构。

# 五、必须遵守的规则

- **保持 DAG**：禁止出现环（例如 A.next 包含 B，同时 B.next 又包含 A），否则流水线无法运行。
- `prev` / `next` 中引用的节点 id 必须真实存在于 `nodes` 中；连接必须双向一致（A 的 next 有 B，则 B 的 prev 必须有 A）。
- 新增节点时 `next`、`prev`、`order`、`x`、`y` 可以先为空或默认值，调用 `format` 后自动补齐；但 `prev`/`next` 是逻辑连接，必须由你正确填写。
- 数据列名必须匹配：消费方 `read_data` 的列名必须是某个上游节点 `write_data` 或输入节点写入的列名；`out_parameters` 引用的 state 键同理。
- 参数必须符合节点类型定义（数值、布尔、字符串、列表都要用正确的 JSON 类型）。
- 不要修改 `category`、`order`、`x`、`y` 等由系统管理的字段。
- 每完成一个明确的编辑目标后，用 `view` 做一次自检，确认无误后再继续，避免一次 patch 改动过大导致错误。

# 六、可用节点类型（node_type 必须取自以下列表）

{node_list}

# 七、实现参考

以下是节点与流水线的完整源码，节点 Parameters 定义、process 语义、字段约束请以源码为准：
```python
{source()}
```"""
