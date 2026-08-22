from __future__ import annotations
from typing import ClassVar, Literal
from pydantic import BaseModel, Field, model_validator, model_serializer
import uuid
import typing
from abc import abstractmethod
import torch
import requests
import csv
import io
from collections import deque
import time
import math
import dotenv
import asyncio
import json
import jinja2
import openai
import os
from datetime import datetime

dotenv.load_dotenv()
Tensor_N: typing.TypeAlias = torch.Tensor


def dynamic_load_client(
    url: str = "http://127.0.0.1:8000/static/client.py",
    save_path: str = "./client.py",
):
    try:
        response = requests.get(url)
        response.raise_for_status()
        script_content = response.text

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(script_content.replace("\r\n", "\n"))
    except Exception as e:
        print(f"Failed to load client from {url}: {str(e)}")


dynamic_load_client()
import client


def tensor_to_text_csv(tensor: list[Tensor_N], column_names: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(column_names)
    for row in zip(*(t.numpy() for t in tensor)):
        writer.writerow(row)
    return buf.getvalue()


def text_csv_to_tensor(
    text_csv: str, with_header: bool = False
) -> tuple[list[Tensor_N], list[str] | None]:
    reader = csv.reader(io.StringIO(text_csv))
    column_names = next(reader) if with_header else None
    rows = [[float(v) for v in row] for row in reader]
    if not rows:
        return [], column_names
    cols = list(zip(*rows))
    return [torch.tensor(col) for col in cols], column_names


class DataView(BaseModel):
    offset_l: int = 0
    offset_r: int = 0
    length: int = -1
    stride: int = 0


class Node(BaseModel):
    _node_registry: ClassVar[dict[str, type["Node"]]] = {}

    def __init_subclass__(cls, **kwargs: typing.Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.model_fields["node_type"].default = cls.__name__
        Node._node_registry[cls.__name__] = cls

    @model_validator(mode="wrap")
    @classmethod
    def _resolve_node_type(
        cls, data: typing.Any, handler: typing.Any, info: typing.Any
    ) -> "Node":
        if cls is not Node:
            return handler(data)
        if isinstance(data, dict):
            node_type = data.get("node_type", "")
            sub_cls = Node._node_registry.get(node_type)
            if sub_cls is not None:
                return sub_cls.model_validate(data)
        return handler(data)

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), pattern=r"^[A-Za-z0-9_-]+$"
    )
    node_type: str = ""
    title: typing.Optional[str] = None
    next: list[str] = Field(
        default_factory=list,
    )
    prev: list[str] = Field(
        default_factory=list,
    )
    x: float = 0
    y: float = 0
    order: int = -1
    read_data: list[str] = Field(
        default_factory=list,
    )
    write_data: list[str] = Field(
        default_factory=list,
    )
    read_state: list[str] = Field(
        default_factory=list,
    )
    write_state: list[str] = Field(
        default_factory=list,
    )

    class Parameters(BaseModel):
        pass

    parameters: Parameters = Parameters()
    category: str = ""

    @abstractmethod
    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        raise NotImplementedError()


class TextCsvInputNode(Node):
    read_data: list[str] = Field(default_factory=list, max_length=0)
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "INPUT"

    class Parameters(BaseModel):
        text_csv: str = "x,y\n1,3\n2,6\n3,7\n4,9\n"
        with_header: bool = True
        overwrite_header: bool = False

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        write_data, column_names = text_csv_to_tensor(
            self.parameters.text_csv, self.parameters.with_header
        )
        if self.parameters.overwrite_header:
            column_names = self.write_data
            return write_data, True
        else:
            context.data.set(column_names, write_data)
            return [], True


class DataOutputNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    category: str = "OUTPUT"

    class Parameters(BaseModel):
        prefix: str = "Data Output: "

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        context.output.append(
            self.parameters.prefix + str([data.tolist() for data in read_data])
        )
        return [], True


class StateOutputNode(Node):
    read_data: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    category: str = "OUTPUT"

    class Parameters(BaseModel):
        prefix: str = "State Output: "

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        reprs = [str(item) for item in context.state.get(self.read_state)]
        context.output.append(self.parameters.prefix + " ".join(reprs))
        return [], True


class AddNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_ROW"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        return [sum(read_data)], True


class AddStateKNode(Node):
    read_state: list[str] = Field(default_factory=list, min_length=1, max_length=1)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_ROW"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        return [
            data + context.state.get(self.read_state[0], 0) for data in read_data
        ], True


class MeanNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_ROW"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        return [sum(read_data) / len(read_data)], True


class ColumnMeanNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_COLUMN"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        for i, col in enumerate(read_data):
            context.state.set(self.write_state[i], col.mean())
        return [], True


class MultiplyNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_ROW"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        result = torch.ones_like(read_data[0])
        for t in read_data:
            result = result * t
        return [result], True


class MultiplyKNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_ROW"

    class Parameters(BaseModel):
        k: float = 1

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        return [data * self.parameters.k for data in read_data], True


class MultiplyStateKNode(Node):
    read_state: list[str] = Field(default_factory=list, min_length=1, max_length=1)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_ROW"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        return [
            data * context.state.get(self.read_state[0], 1) for data in read_data
        ], True


class SendAlarmNode(Node):
    read_data: list[str] = Field(default_factory=list, max_length=0)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "ALARM"

    class Parameters(BaseModel):
        instance: str = ""
        raw_data: str = "data"

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        alarms = []
        for alarm_item in context.alarm.values:
            alarms.append(
                {
                    "instance_id": self.parameters.instance,
                    "range_from": alarm_item.range[0],
                    "range_to": alarm_item.range[1],
                    "cols": alarm_item.cols,
                    "message": alarm_item.message,
                    "raw_data": self.parameters.raw_data,
                    "time": str(datetime.now()),
                    "level": alarm_item.level,
                }
            )
        client.analysis.alarm.adds(alarms)
        return [], True


class AlarmIfNumberStateKNode(Node):
    read_data: list[str] = Field(default_factory=list, min_length=1)
    read_state: list[str] = Field(default_factory=list, min_length=1)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    category: str = "ALARM"

    class Parameters(BaseModel):
        threshold: float = 0
        comparison: Literal["eq", "lt", "gt", "le", "ge"] = "eq"
        condition: Literal["any", "all"] = "any"
        jinja_prompt: str = "Alarm: {{ state }}"
        level: int = 1

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        threshold = self.parameters.threshold
        ops = {
            "eq": lambda v: v == threshold,
            "lt": lambda v: v < threshold,
            "gt": lambda v: v > threshold,
            "le": lambda v: v <= threshold,
            "ge": lambda v: v >= threshold,
        }
        values = context.state.get(self.read_state)
        results = [bool(ops[self.parameters.comparison](v)) for v in values]
        triggered = any(results) if self.parameters.condition == "any" else all(results)
        context.state.set(self.write_state, triggered)
        if triggered:
            data_ctx: dict[str, typing.Any] = {}
            for k, v in context.data.values.items():
                data_ctx[k] = v.tolist() if isinstance(v, torch.Tensor) else v
            state_ctx: dict[str, typing.Any] = dict(context.state.values)
            message = (
                jinja2.Environment()
                .from_string(self.parameters.jinja_prompt)
                .render(data=data_ctx, state=state_ctx)
            )
            max_len = max(len(col) for col in read_data)
            context.alarm.add(
                AlarmItem(
                    cols=self.read_data,
                    range=(0, max_len),
                    message=message,
                    level=self.parameters.level,
                )
            )
        return [], True


class SubtractNode(Node):
    read_data: list[str] = Field(default_factory=list, min_length=2, max_length=2)
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_ROW"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        return [read_data[0] - read_data[1]], True


class DivideNode(Node):
    read_data: list[str] = Field(default_factory=list, min_length=2, max_length=2)
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_ROW"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        return [read_data[0] / read_data[1]], True


class PowerKNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_ROW"

    class Parameters(BaseModel):
        exponent: float = 1

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        return [data.pow(self.parameters.exponent) for data in read_data], True


class WriteStateKNode(Node):
    read_data: list[str] = Field(default_factory=list, max_length=0)
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    category: str = "STATE"

    class Parameters(BaseModel):
        value: typing.Any = 0

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        context.state.set(self.write_state, self.parameters.value)
        return [], True


class PearsonNode(Node):
    read_data: list[str] = Field(default_factory=list, min_length=2, max_length=2)
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_COLUMN"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        x, y = read_data
        x = x - x.mean()
        y = y - y.mean()
        r = (x * y).sum() / torch.sqrt((x * x).sum() * (y * y).sum())
        context.state.set(self.write_state, float(r))
        return [], True


class RoundNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_COLUMN"

    class Parameters(BaseModel):
        decimals: int = Field(default=4, ge=0)

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        write_data = [
            torch.round(tensor, decimals=self.parameters.decimals)
            for tensor in read_data
        ]
        for key in self.write_data:
            context.data.decimals[key] = self.parameters.decimals
        return write_data, True


class VarNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_COLUMN"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        for i, k in enumerate(self.write_state):
            context.state.set(k, float(read_data[i].var()))
        return [], True


class StdNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    category: str = "BY_COLUMN"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        for i, k in enumerate(self.write_state):
            context.state.set(k, float(read_data[i].std()))
        return [], True


class OLSRegressionNode(Node):
    read_data: list[str] = Field(default_factory=list, min_length=2, max_length=2)
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, min_length=2, max_length=2)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    category: str = "REGRESSION"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        x = read_data[0]
        y = read_data[1]
        x_mean = x.mean()
        y_mean = y.mean()
        k = ((x - x_mean) * (y - y_mean)).sum() / ((x - x_mean) ** 2).sum()
        b = y_mean - k * x_mean
        context.state.set(self.write_state[0], float(k))
        context.state.set(self.write_state[1], float(b))
        return [], True


class DemingRegressionNode(Node):
    read_data: list[str] = Field(default_factory=list, min_length=2, max_length=2)
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, min_length=2, max_length=2)
    write_data: list[str] = Field(default_factory=list, max_length=0)
    category: str = "REGRESSION"

    class Parameters(BaseModel):
        lambda_: float = Field(default=1, alias="lambda")

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        x = read_data[0]
        y = read_data[1]
        lambda_ = self.parameters.lambda_
        x_mean = x.mean()
        y_mean = y.mean()

        dx = x - x_mean
        dy = y - y_mean

        sxx = (dx * dx).mean()
        syy = (dy * dy).mean()
        sxy = (dx * dy).mean()

        delta = syy - lambda_ * sxx

        beta1 = (delta + torch.sqrt(delta**2 + 4 * lambda_ * sxy**2)) / (2 * sxy)

        beta0 = y_mean - beta1 * x_mean
        context.state.set(self.write_state[0], float(beta0))
        context.state.set(self.write_state[1], float(beta1))
        return [], True


class ShewharNode(Node):
    read_data: list[str] = Field(default_factory=list, max_length=1)
    read_state: list[str] = Field(default_factory=list, max_length=0)
    write_state: list[str] = Field(default_factory=list, max_length=0)

    class Parameters(BaseModel):
        mu_key: str = ""
        sigma_key: str = ""
        ratio: float = 3

    parameters: Parameters = Parameters()
    category: str = "BY_ROW"

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        data = read_data[0]
        mu = context.state.get(self.parameters.mu_key)
        sigma = context.state.get(self.parameters.sigma_key)
        upper = mu + self.parameters.ratio * sigma
        lower = mu - self.parameters.ratio * sigma
        out_of_control = ((data < lower) | (data > upper)).float()
        return [out_of_control], True


class InferenceNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)

    category: str = "REMOTE"

    class Parameters(BaseModel):
        instance: str = ""

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        text_csv = tensor_to_text_csv(read_data, self.read_data)
        result = client.highlevel.infer_text_csv(
            self.parameters.instance, text_csv, self.read_data
        )
        print(result)
        result = result["result"][0]
        result_outputs = result["outputs"]
        result_loss = result["loss"]
        result_ids = result["ids"]
        write_data = []
        context.state.set(self.write_state, result_loss)
        for col in range(len(self.write_data)):
            write_data.append(torch.full((len(read_data[0]),), torch.nan))
        for row, row_id in enumerate(result_ids):
            for col in range(len(self.write_data)):
                write_data[col][row_id] = result_outputs[row][col]
        return write_data, True


class TrainNode(Node):
    read_state: list[str] = Field(default_factory=list, max_length=0)

    category: str = "REMOTE"

    class Parameters(BaseModel):
        instance: str = ""
        epoch: int = 1
        learning_rate: float = 1e-3
        batch_size: int = 1
        device: str = "cpu"
        data_cols: list[str] = Field(default_factory=list)
        label_cols: list[str] = Field(default_factory=list)

    parameters: Parameters = Parameters()

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        text_csv = tensor_to_text_csv(read_data, self.read_data)
        result = client.highlevel.train_text_csv(
            self.parameters.instance,
            text_csv,
            self.parameters.data_cols,
            self.parameters.label_cols,
            self.parameters.epoch,
            self.parameters.learning_rate,
            self.parameters.device,
            self.parameters.batch_size,
        )
        print(result)
        result = result["result"][0]
        result_outputs = result["outputs"]
        result_loss = result["loss"]
        result_ids = result["ids"]
        write_data = []
        context.state.set(self.write_state, result_loss)
        for col in range(len(self.write_data)):
            write_data.append(torch.full((len(read_data[0]),), torch.nan))
        for row, row_id in enumerate(result_ids):
            for col in range(len(self.write_data)):
                write_data[col][row_id] = result_outputs[row][col]
        return write_data, True


class LLMNode(Node):
    category: str = "REMOTE"
    write_data: list[str] = Field(default_factory=list, max_length=0)
    read_data: list[str] = Field(default_factory=list, max_length=0)
    read_state: list[str] = Field(default_factory=list, max_length=0)

    class Parameters(BaseModel):
        response_api: bool = True
        openai_api_key: str = os.environ["OPENAI_API_KEY"]
        openai_base_url: str = os.environ["OPENAI_BASE_URL"]
        openai_model_name: str = os.environ["OPENAI_MODEL_NAME"]
        return_json: bool = True
        jinja_prompt: str = "Hello"
        reasoning: bool = False
        reasoning_state: str = ""

    parameters: Parameters = Field(default_factory=Parameters)

    def process(
        self, read_data: list[Tensor_N], context: Context
    ) -> tuple[list[Tensor_N], bool]:
        data_ctx: dict[str, typing.Any] = {}
        for k, v in context.data.values.items():
            data_ctx[k] = v.tolist() if isinstance(v, torch.Tensor) else v

        state_ctx: dict[str, typing.Any] = dict(context.state.values)
        template = jinja2.Environment().from_string(self.parameters.jinja_prompt)
        prompt = template.render(data=data_ctx, state=state_ctx)
        client = openai.OpenAI(
            api_key=self.parameters.openai_api_key,
            base_url=self.parameters.openai_base_url,
        )

        content = ""
        reasoning_text = ""

        if self.parameters.response_api:
            create_kwargs: dict[str, typing.Any] = {
                "model": self.parameters.openai_model_name,
                "input": prompt,
            }
            if self.parameters.reasoning:
                create_kwargs["reasoning"] = {"effort": "max"}
                create_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            if self.parameters.return_json:
                create_kwargs["text"] = {"format": {"type": "json_object"}}
            response = client.responses.create(**create_kwargs)
            content = response.output_text
            if self.parameters.reasoning:
                try:
                    for item in response.output:
                        if getattr(item, "type", None) == "reasoning":
                            summaries = getattr(item, "summary", [])
                            if summaries:
                                reasoning_text = " ".join(
                                    getattr(s, "text", str(s)) for s in summaries
                                )
                                break
                except Exception:
                    pass
        else:
            create_kwargs: dict[str, typing.Any] = {
                "model": self.parameters.openai_model_name,
                "messages": [{"role": "user", "content": prompt}],
            }
            if self.parameters.reasoning:
                create_kwargs["reasoning_effort"] = "medium"
                create_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            if self.parameters.return_json:
                create_kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**create_kwargs)
            content = response.choices[0].message.content or ""
            if self.parameters.reasoning:
                try:
                    reasoning_text = getattr(
                        response.choices[0].message, "reasoning_content", ""
                    )
                except Exception:
                    pass
        if self.parameters.reasoning and self.parameters.reasoning_state:
            context.state.set(self.parameters.reasoning_state, reasoning_text)
        if self.parameters.return_json:
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    for k in self.write_state:
                        if k in parsed:
                            context.state.set(k, parsed[k])
                else:
                    context.state.set(self.write_state, content)
            except (json.JSONDecodeError, ValueError):
                context.state.set(self.write_state, content)
        else:
            context.state.set(self.write_state, content)

        return [], True


def get_all_node_cls() -> list[type[Node]]:
    return list(Node._node_registry.values())


class Pipeline(BaseModel):
    name: typing.Optional[str] = ""
    cron_expr: str = ""
    cron_enable: bool = False
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), pattern=r"^[A-Za-z0-9_-]+$"
    )
    nodes: dict[str, Node] = Field(default_factory=dict[str, Node])
    return_data: list[str] = Field(default_factory=list)
    return_state: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _ser_nodes(
        self, handler: typing.Any, info: typing.Any
    ) -> dict[str, typing.Any]:
        result = handler(self)
        result["nodes"] = {
            nid: node.model_dump(mode=info.mode if info else "python", by_alias=True)
            for nid, node in self.nodes.items()
        }
        return result

    def update_prev_next(self):
        for node in self.nodes.values():
            for prev_id in node.prev:
                if prev_id in self.nodes and node.id not in self.nodes[prev_id].next:
                    self.nodes[prev_id].next.append(node.id)
            for next_id in node.next:
                if next_id in self.nodes and node.id not in self.nodes[next_id].prev:
                    self.nodes[next_id].prev.append(node.id)

    def update_order(self):
        queue = deque([nid for nid, node in self.nodes.items() if not node.prev])
        visited = set()
        while queue:
            nid = queue.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            node = self.nodes[nid]
            if not node.prev:
                node.order = 0
            else:
                node.order = (
                    max(self.nodes[pid].order for pid in node.prev if pid in self.nodes)
                    + 1
                )
            for next_id in node.next:
                if next_id in self.nodes and next_id not in visited:
                    all_prev_visited = all(
                        pid in visited
                        for pid in self.nodes[next_id].prev
                        if pid in self.nodes
                    )
                    if all_prev_visited:
                        queue.append(next_id)

    def update_xy(self, width: float = 1.0, height: float = 1.0):
        order_groups: dict[int, list[Node]] = {}
        for node in self.nodes.values():
            order_groups.setdefault(node.order, []).append(node)

        for order in sorted(order_groups.keys()):
            for i, node in enumerate(order_groups[order]):
                node.x = order * width
                node.y = i * height

    def add_node(self, node: Node):
        self.nodes[node.id] = node

    def add_nodes(self, nodes: list[Node]):
        for node in nodes:
            self.add_node(node)

    def is_dag(self) -> bool:
        in_degree: dict[str, int] = {}
        for nid, node in self.nodes.items():
            in_degree[nid] = len([p for p in node.prev if p in self.nodes])

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            nid = queue.popleft()
            visited_count += 1
            for next_id in self.nodes[nid].next:
                if next_id in in_degree:
                    in_degree[next_id] -= 1
                    if in_degree[next_id] == 0:
                        queue.append(next_id)

        return visited_count == len(self.nodes)

    def load_init(
        self,
        init_data: dict[str, list[typing.Any]] | None = None,
        init_state: dict[str, typing.Any] | None = None,
    ) -> Context:
        context = Context()
        if init_data:
            for k, v in init_data.items():
                context.data.values[k] = torch.tensor(v, dtype=torch.float32)
        if init_state:
            for k, v in init_state.items():
                context.state.values[k] = v
        return context

    def run(
        self,
        update_prev_next: bool = True,
        update_order: bool = True,
        init_data: dict[str, list[typing.Any]] | None = None,
        init_state: dict[str, typing.Any] | None = None,
        pipeline_id: str | None = None,
        cron_expr: str | None = None,
        executed_at: typing.Any = None,
    ) -> Context:
        if update_prev_next:
            self.update_prev_next()
        if update_order:
            self.update_order()

        if not self.is_dag():
            raise ValueError("Pipeline is not a DAG")

        context = self.load_init(init_data, init_state)
        if pipeline_id is not None:
            context.pipeline_id = pipeline_id
        if cron_expr is not None:
            context.cron_expr = cron_expr
        if executed_at is not None:
            context.executed_at = executed_at
        order_groups: dict[int, list[Node]] = {}
        for node in self.nodes.values():
            order_groups.setdefault(node.order, []).append(node)
        skipped: set[str] = set()
        t0 = time.perf_counter()
        for order in sorted(order_groups.keys()):
            for node in order_groups[order]:
                if node.id in skipped:
                    continue
                context.performance.record_start(
                    node.id, node.title or "", (time.perf_counter() - t0) * 1000
                )
                read_data = context.data.get(node.read_data) if node.read_data else []
                result, should_continue = node.process(read_data, context)
                if not should_continue:
                    queue = deque(node.next)
                    while queue:
                        nid = queue.popleft()
                        if nid not in skipped and nid in self.nodes:
                            skipped.add(nid)
                            queue.extend(self.nodes[nid].next)
                    continue
                if result and node.write_data:
                    context.data.set(node.write_data, result)
                context.performance.record_end(
                    node.id, (time.perf_counter() - t0) * 1000
                )
        return context

    async def arun(
        self,
        update_prev_next: bool = True,
        update_order: bool = True,
        init_data: dict[str, list[typing.Any]] | None = None,
        init_state: dict[str, typing.Any] | None = None,
        pipeline_id: str | None = None,
        cron_expr: str | None = None,
        executed_at: typing.Any = None,
    ) -> Context:
        return await asyncio.to_thread(
            self.run,
            update_prev_next,
            update_order,
            init_data,
            init_state,
            pipeline_id,
            cron_expr,
            executed_at,
        )


class Data:
    values: dict[str, Tensor_N]
    decimals: dict[str, int]

    def __init__(self):
        self.values = {}
        self.decimals = {}

    def get(self, k: list[str]) -> list[Tensor_N]:
        if not isinstance(k, list):
            k = [k]
        return [self.values[key] for key in k]

    def set(self, k: list[str], v: list[Tensor_N]):
        for i, key in enumerate(k):
            self.values[key] = v[i]


class State:
    values: dict[str, typing.Any]

    def __init__(self):
        self.values = {}

    def set(self, k: str | list[str], v: typing.Any):
        if isinstance(k, list):
            for ik in k:
                self.values[ik] = v
        else:
            self.values[k] = v

    def get(self, k: str | list[str], default: typing.Any = 0) -> typing.Any:
        if isinstance(k, list):
            results = []
            for ik in k:
                results.append(self.values.get(ik, default))
            return results
        return self.values.get(k, default)


class AlarmItem(BaseModel):
    cols: list[str]
    range: tuple[int, int]
    message: str
    level: int


class Alarm:
    values: list[AlarmItem]

    def __init__(self):
        self.values = []

    def add(self, v: AlarmItem):
        self.values.append(v)

    def dump(self) -> list[dict]:
        return [item.model_dump() for item in self.values]


class NodeTiming(BaseModel):
    start_time: float = 0.0
    end_time: float = 0.0
    interval: float = 0.0
    title: str = ""


class Performance(BaseModel):
    timings: dict[str, NodeTiming] = Field(default_factory=dict)

    def record_start(self, node_id: str, title: str, t: float):
        if node_id not in self.timings:
            self.timings[node_id] = NodeTiming()
        timing = self.timings[node_id]
        timing.start_time = t
        timing.title = title

    def record_end(self, node_id: str, t: float):
        if node_id not in self.timings:
            self.timings[node_id] = NodeTiming()
        timing = self.timings[node_id]
        timing.end_time = t
        timing.interval = t - timing.start_time

    def get(self, node_id: str) -> NodeTiming | None:
        return self.timings.get(node_id)

    def dump_pretty(self):
        if not self.timings:
            return
        print(
            f"{'Node':<20} {'Title':<20} {'Start(ms)':>12} {'End(ms)':>12} {'Interval(ms)':>12}"
        )
        print("-" * 82)
        for node_id, t in self.timings.items():
            print(
                f"{node_id:<20} {t.title:<20} {t.start_time:>12.3f} {t.end_time:>12.3f} {t.interval:>12.3f}"
            )

    def dump(self) -> list[dict]:
        return [
            {
                "node": node_id,
                "title": t.title,
                "start_time": t.start_time,
                "end_time": t.end_time,
                "interval": t.interval,
            }
            for node_id, t in self.timings.items()
        ]


class Context:
    data: Data
    state: State
    alarm: Alarm
    performance: Performance
    output: list[str]

    def __init__(self):
        self.data = Data()
        self.state = State()
        self.alarm = Alarm()
        self.performance = Performance()
        self.output = list[str]()

    def dump(
        self,
        return_data: list[str] | None = None,
        return_state: list[str] | None = None,
    ) -> dict:
        def _apply_rounding(obj, decimals: int):
            if isinstance(obj, list):
                return [_apply_rounding(item, decimals) for item in obj]
            elif isinstance(obj, float):
                return round(obj, decimals)
            return obj

        def _convert_tensor(t: torch.Tensor, decimals: int | None = None):
            arr = t.tolist()
            arr = _replace_nan(arr)
            if decimals is not None:
                arr = _apply_rounding(arr, decimals)
            return arr

        def _replace_nan(obj):
            if isinstance(obj, list):
                return [_replace_nan(item) for item in obj]
            elif isinstance(obj, float) and math.isnan(obj):
                return "NaN"
            return obj

        def _convert_state_value(v):
            if isinstance(v, torch.Tensor):
                return _convert_tensor(v)
            elif isinstance(v, float) and math.isnan(v):
                return "NaN"
            elif isinstance(v, list):
                return _replace_nan(v)
            else:
                return repr(v)

        data_keys = (
            return_data if return_data is not None else list(self.data.values.keys())
        )
        state_keys = (
            return_state if return_state is not None else list(self.state.values.keys())
        )

        return {
            "data": {
                k: _convert_tensor(
                    self.data.values[k],
                    self.data.decimals.get(k),
                )
                for k in data_keys
                if k in self.data.values
            },
            "state": {
                k: _convert_state_value(self.state.values[k])
                for k in state_keys
                if k in self.state.values
            },
            "alarm": self.alarm.dump(),
            "performance": self.performance.dump(),
            "output": self.output,
        }


def source() -> str:
    return open(__file__, "r", encoding="utf-8").read()


if __name__ == "__main__":
    p = Pipeline(id="example")
    p.add_nodes(
        [
            TextCsvInputNode(
                id="raw", parameters=TextCsvInputNode.Parameters(with_header=True)
            ),
            TextCsvInputNode(
                id="pred",
                parameters=TextCsvInputNode.Parameters(text_csv="pred_x\n5\n6\n7\n8\n"),
            ),
            OLSRegressionNode(
                id="ols", prev=["raw"], read_data=["x", "y"], write_state=["k", "b"]
            ),
            StateOutputNode(id="k_b", prev=["ols"], read_state=["k", "b"]),
            MultiplyStateKNode(
                id="kx",
                prev=["pred", "ols"],
                read_data=["pred_x"],
                write_data=["pred_y"],
                read_state=["k"],
            ),
            DataOutputNode(id="kx_out", prev=["kx"], read_data=["pred_y"]),
            AddStateKNode(
                id="kx_b",
                prev=["kx"],
                read_data=["pred_y"],
                write_data=["pred_y"],
                read_state=["b"],
            ),
            DataOutputNode(id="kx_b_out", read_data=["pred_y"], prev=["kx_b"]),
            PearsonNode(
                id="pearson", prev=["raw"], read_data=["x", "y"], write_state=["rho"]
            ),
            StateOutputNode(id="rho", prev=["pearson"], read_state=["rho"]),
        ]
    )
    print(p.model_dump_json(indent=4))
    ctx = p.run()
    print("\n".join(ctx.output))
    ctx.performance.dump_pretty()
