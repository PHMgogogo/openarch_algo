import base
import os
import asyncio
import glob
import shutil
import typing
from datetime import datetime
from croniter import croniter
from pydantic import BaseModel


class CronContextItem(BaseModel):
    filename: str
    executed_at: str | None


class CronStatusItem(BaseModel):
    pipeline_id: str
    running: bool
    last_run: str | None
    cron_expr: str


class CronNextTime(BaseModel):
    pipeline_id: str
    cron_enabled: bool
    cron_expr: str | None = None
    next: str | None = None


class CronExecutionResult(BaseModel):
    pipeline_id: str
    cron_expr: str
    executed_at: str
    data: dict[str, typing.Any] = {}
    state: dict[str, typing.Any] = {}
    alarm: list[dict[str, typing.Any]] = []
    performance: list[dict[str, typing.Any]] = []
    output: list[str] = []


class CronEntry:
    def __init__(self):
        self.task: asyncio.Task | None = None
        self.last_run: datetime | None = None

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    @property
    def idle(self) -> bool:
        return self.task is None or self.task.done()


class Config:
    pipeline_path: str = "./pipeline"
    cron_context_path: str = "./cron_context"
    max_history: int = 100


class PipelineManager:
    crons: dict[str, CronEntry]

    def __init__(self):
        os.makedirs(Config.pipeline_path, exist_ok=True)
        os.makedirs(Config.cron_context_path, exist_ok=True)
        self.crons = {}
        for pid in self.list_pipeline():
            pipeline = self.get_pipeline(pid)
            if pipeline.cron_enable and pipeline.cron_expr:
                self.crons[pid] = CronEntry()

    def list_pipeline(self) -> list[str]:
        target_path = Config.pipeline_path
        filenames = os.listdir(target_path)
        results = []
        for fn in filenames:
            results.append(fn.split(".")[0])
        return results

    def get_pipeline(self, id: str) -> base.Pipeline:
        return base.Pipeline.model_validate_json(
            open(
                os.path.join(Config.pipeline_path, f"{id}.json"), encoding="utf-8"
            ).read()
        )

    def _should_run_cron(self, cron_expr: str, pipeline_id: str) -> bool:
        now = datetime.now()
        cron = croniter(cron_expr, now)
        prev = cron.get_prev(datetime)
        entry = self.crons.get(pipeline_id)
        if entry is None or entry.last_run is None:
            return True
        return prev > entry.last_run

    async def _run_pipeline_and_dump(self, pipeline: base.Pipeline, executed_at: datetime):
        try:
            context = await pipeline.arun(
                pipeline_id=pipeline.id,
                cron_expr=pipeline.cron_expr,
                executed_at=executed_at,
            )
            dumped = context.dump(
                return_data=pipeline.return_data,
                return_state=pipeline.return_state,
            )
            result = CronExecutionResult(
                pipeline_id=pipeline.id,
                cron_expr=pipeline.cron_expr,
                executed_at=executed_at.isoformat(),
                data=dumped.get("data", {}),
                state=dumped.get("state", {}),
                alarm=dumped.get("alarm", []),
                performance=dumped.get("performance", []),
                output=dumped.get("output", []),
            )
            ts = executed_at.strftime("%Y%m%dT%H%M%S")
            dirpath = os.path.join(Config.cron_context_path, pipeline.id)
            os.makedirs(dirpath, exist_ok=True)
            filepath = os.path.join(dirpath, f"{ts}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(result.model_dump_json(ensure_ascii=False, indent=2))
            self._trim_history(pipeline.id)
        except Exception as e:
            print(f"[cron] Pipeline {pipeline.id} run failed: {e}")

    def _trim_history(self, pipeline_id: str):
        dirpath = os.path.join(Config.cron_context_path, pipeline_id)
        if not os.path.isdir(dirpath):
            return
        files = sorted(
            glob.glob(os.path.join(dirpath, "*.json")),
            key=os.path.getmtime,
        )
        while len(files) > Config.max_history:
            os.unlink(files.pop(0))

    async def cron_loop(self):
        while True:
            try:
                current_ids = set(self.list_pipeline())

                for pid in current_ids:
                    try:
                        pipeline = self.get_pipeline(pid)
                    except Exception:
                        continue

                    if not pipeline.cron_enable or not pipeline.cron_expr:
                        entry = self.crons.get(pid)
                        if entry is not None and entry.idle:
                            del self.crons[pid]
                        continue

                    if self._should_run_cron(pipeline.cron_expr, pid):
                        if pid not in self.crons:
                            self.crons[pid] = CronEntry()

                        entry = self.crons[pid]
                        if entry.idle:
                            now = datetime.now()
                            entry.task = asyncio.create_task(
                                self._run_pipeline_and_dump(pipeline, now)
                            )
                            entry.last_run = now
                    else:
                        if pid not in self.crons:
                            self.crons[pid] = CronEntry()
                for pid in list(self.crons.keys()):
                    if pid not in current_ids:
                        entry = self.crons[pid]
                        if entry.idle:
                            del self.crons[pid]

            except Exception as e:
                print(f"[cron] Error: {e}")

            await asyncio.sleep(30)

    def save_pipeline(self, pipeline: base.Pipeline) -> None:
        open(
            os.path.join(Config.pipeline_path, f"{pipeline.id}.json"),
            "w",
            encoding="utf-8",
        ).write(pipeline.model_dump_json(by_alias=True, ensure_ascii=False, indent=2))

    def del_pipeline(self, id: str):
        os.unlink(os.path.join(Config.pipeline_path, f"{id}.json"))
        dirpath = os.path.join(Config.cron_context_path, id)
        if os.path.isdir(dirpath):
            shutil.rmtree(dirpath)
        if id in self.crons:
            del self.crons[id]

    def rename_pipeline(self, old_id: str, new_id: str):
        pipeline = self.get_pipeline(old_id)
        pipeline.id = new_id
        self.save_pipeline(pipeline)
        self.del_pipeline(old_id)

    def list_cron_contexts(self, pipeline_id: str) -> list[CronContextItem]:
        dirpath = os.path.join(Config.cron_context_path, pipeline_id)
        if not os.path.isdir(dirpath):
            return []
        results = []
        for f in sorted(glob.glob(os.path.join(dirpath, "*.json"))):
            basename = os.path.basename(f)
            ts_str = basename[:-5]
            try:
                executed_at = datetime.strptime(ts_str, "%Y%m%dT%H%M%S").isoformat()
            except ValueError:
                executed_at = None
            results.append(CronContextItem(filename=basename, executed_at=executed_at))
        return results

    def get_cron_context(self, pipeline_id: str, filename: str) -> CronExecutionResult:
        filepath = os.path.join(Config.cron_context_path, pipeline_id, filename)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Cron context not found: {filename}")
        with open(filepath, "r", encoding="utf-8") as f:
            return CronExecutionResult.model_validate_json(f.read())

    def get_cron_status(self) -> list[CronStatusItem]:
        results = []
        for pid, entry in self.crons.items():
            try:
                pipeline = self.get_pipeline(pid)
                cron_expr = pipeline.cron_expr
            except Exception:
                cron_expr = ""
            results.append(CronStatusItem(
                pipeline_id=pid,
                running=entry.running,
                last_run=entry.last_run.isoformat() if entry.last_run else None,
                cron_expr=cron_expr,
            ))
        return results

    def get_next_cron_time(self, pipeline_id: str) -> CronNextTime:
        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline.cron_enable or not pipeline.cron_expr:
            return CronNextTime(
                pipeline_id=pipeline_id,
                cron_enabled=False,
            )
        now = datetime.now()
        cron = croniter(pipeline.cron_expr, now)
        next_time = cron.get_next(datetime)
        return CronNextTime(
            pipeline_id=pipeline_id,
            cron_enabled=True,
            cron_expr=pipeline.cron_expr,
            next=next_time.isoformat(),
        )


if __name__ == "__main__":
    from base import *

    pm = PipelineManager()
    p = base.Pipeline(id="deming")
    p.add_nodes(
        [
            TextCsvInputNode(
                id="raw", parameters=TextCsvInputNode.Parameters(with_header=True)
            ),
            TextCsvInputNode(
                id="pred",
                parameters=TextCsvInputNode.Parameters(text_csv="pred_x\n5\n6\n7\n8\n"),
            ),
            DemingRegressionNode(
                id="deming", prev=["raw"], read_data=["x", "y"], write_state=["k", "b"]
            ),
            StateOutputNode(id="k_b", prev=["deming"], read_state=["k", "b"]),
            MultiplyStateKNode(
                id="kx",
                prev=["pred", "deming"],
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
    p.update_prev_next()
    p.update_order()
    pm.save_pipeline(p)
    print(pm.get_pipeline(p.id))
    print(pm.list_pipeline())
