from fastapi import HTTPException
from pdb import pm
import fastapi_reverse_proxy as frp
from enum import Enum, auto
import re
from fastapi import Request, WebSocket, FastAPI, APIRouter
from fastapi.responses import PlainTextResponse, FileResponse
from pydantic import BaseModel, Field
import uuid
import json
import os
from contextlib import asynccontextmanager
from filelock import FileLock
import asyncio


def get_bool_env_strict(value: str):
    value = value.strip().lower()
    if value in ("true", "1", "yes", "on"):
        return True
    return False


PROXY_RULE_PATH = os.path.abspath(os.environ.get("PROXY_RULE_PATH", "./rules.json"))
PROXY_LOCK_PATH = os.path.abspath(
    os.environ.get("PROXY_LOCK_PATH", "./rules.json.lock")
)
EXPOSE_SERVICE_MANAGER = get_bool_env_strict(
    os.environ.get("EXPOSE_SERVICE_MANAGER", "true")
)
SERVICE_MANAGER_API = os.environ.get("SERVICE_MANAGER_API", "/smgr")
# proxy_lock = AsyncFileLock(PROXY_LOCK_PATH)


class RuleType(str, Enum):
    EXACT = auto()
    PREFIX = auto()
    REGEX = auto()


class UrlProxyRule(BaseModel):
    name: str = Field(
        default_factory=lambda: str(uuid.uuid4()), pattern=r"^[A-Za-z0-9_-]+$"
    )
    order: int = -1
    rule_type: RuleType = RuleType.EXACT
    pattern: str | re.Pattern = ""
    dest_index: list[int] | None = None
    dest_format: str = None
    rewrite_host: str | None = None
    editable: bool = True
    timeout: float | None = None
    enable: bool = True
    file_serve_root_path: str | None = None

    def model_post_init(self, context):
        if self.dest_index is None and self.rule_type == RuleType.EXACT:
            self.dest_index = [0]
        if self.dest_index is None and self.rule_type == RuleType.PREFIX:
            self.dest_index = [1]
        if self.dest_index is None and self.rule_type == RuleType.REGEX:
            self.dest_index = [0]
        if self.dest_format is None and self.rule_type == RuleType.EXACT:
            self.dest_format = "%s"
        if self.dest_format is None and self.rule_type == RuleType.PREFIX:
            self.dest_format = "%s"
        if self.dest_format is None and self.rule_type == RuleType.REGEX:
            self.dest_format = "%s"

    def dest(self, path: str) -> str:
        result, groups = self.match(path)
        if not result:
            return ""
        else:
            tuples = tuple(groups[idx] for idx in self.dest_index)
            return self.dest_format % tuples

    def host(self, raw_host: str) -> str:
        if self.rewrite_host is None:
            return raw_host
        else:
            return self.rewrite_host

    def match(self, path: str) -> tuple[bool, list[str]]:
        if self.rule_type == RuleType.EXACT:
            return self._exact_match(path)
        elif self.rule_type == RuleType.PREFIX:
            return self._prefix_match(path)
        elif self.rule_type == RuleType.REGEX:
            return self._regex_match(path)

    def _exact_match(self, path: str) -> tuple[bool, list[str]]:
        result = self.pattern == path
        if result:
            return True, [path]
        return False, []

    def _prefix_match(self, path: str) -> tuple[bool, list[str]]:
        result = path.startswith(self.pattern)
        if result:
            l = len(self.pattern)
            return True, [path[:l], path[l:]]
        return False, []

    def _regex_match(self, path: str) -> tuple[bool, list[str]]:
        result = re.match(self.pattern, path)
        if not result:
            return False, []

        groups = result.groups()
        return True, list(groups) if groups else [result.group()]


class PathRequest(BaseModel):
    path: str


class UprTryRequest(BaseModel):
    path: str
    upr: UrlProxyRule
    host: str


class ServiceManager:
    _rules: dict[str, UrlProxyRule]
    _sorted_rules: list[UrlProxyRule]
    proxy_lock = FileLock(PROXY_LOCK_PATH)

    def __init__(self):
        self._rules = dict[str, UrlProxyRule]()
        self._sorted_rules = list[UrlProxyRule]()
        # await self.load_from()

    async def save_to(self, path: str = PROXY_RULE_PATH):
        with self.proxy_lock:
            open(path, "w", encoding="utf-8").write(self.save())

    def save(self) -> str:
        obj = [rule.model_dump() for rule in self._rules.values()]
        return json.dumps(obj, ensure_ascii=False, indent=4)

    def _sort(self):
        self._sorted_rules = sorted(
            [rule for rule in self._rules.values() if rule.enable],
            key=lambda r: r.order,
            reverse=True,
        )

    async def flush(self):
        self._sort()
        await self.save_to()

    async def load_from(self, path: str = PROXY_RULE_PATH):
        with self.proxy_lock:
            if not os.path.exists(path):
                self.load("[]")
            self.load(open(path, encoding="utf-8").read())

    def load(self, json_str: str):
        obj: dict = json.loads(json_str)
        self._rules.clear()
        for item in obj:
            rule: UrlProxyRule = UrlProxyRule.model_validate(item)
            self._rules[rule.name] = rule
        self._sort()

    def get(self, name: str) -> UrlProxyRule:
        return self._rules.get(name)

    async def add(self, upr: UrlProxyRule, update: bool = True) -> None:
        with self.proxy_lock:
            await self.load_from()
            if upr.name in self._rules:
                if not self._rules[upr.name].editable:
                    return
            self._rules[upr.name] = upr
            await self.flush()

    async def delete(self, name: str) -> None:
        with self.proxy_lock:
            await self.load_from()
            if name in self._rules and self._rules[name].editable:
                del self._rules[name]
                await self.flush()

    def match(self, path: str) -> tuple[UrlProxyRule | None, str]:
        for rule in self._sorted_rules:
            dest = rule.dest(path)
            if dest:
                return rule, dest
        return None, ""

    def list(self) -> list[UrlProxyRule]:
        return list(self._rules.values())

    async def reload_loop(self, reload_interval: float = 5):
        while True:
            try:
                await asyncio.sleep(reload_interval)
            finally:
                pass
            try:
                await self.load_from()
            finally:
                pass


def safe_file_response(path: str):
    if not os.path.exists(path):
        return PlainTextResponse("File not found", status_code=404)

    if not os.path.isfile(path):
        return PlainTextResponse("Invalid file", status_code=400)

    return FileResponse(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.sm = ServiceManager()
    await post_init(app)

    @app.api_route(
        "{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    )
    async def gateway(request: Request, path: str):
        try:
            upr, dest = app.sm.match(path)
        except:
            return PlainTextResponse("no match", status_code=404)
        if upr.file_serve_root_path is not None:
            if request.method != "GET":
                return PlainTextResponse("wrong request type", status_code=405)
            return safe_file_response(os.path.join(upr.file_serve_root_path, dest))
        raw_host = request.headers.get("host")
        host = upr.host(raw_host)
        if host == raw_host:
            return PlainTextResponse("loop", status_code=508)
        return await frp.proxy_pass(request, host, dest, upr.timeout)

    @app.websocket("{path:path}")
    async def ws_gateway(websocket: WebSocket, path: str):
        try:
            upr, dest = app.sm.match(path)
            raw_host = websocket.headers.get("host")
            host = upr.host(raw_host)
            if host == raw_host:
                return PlainTextResponse("loop", status_code=508)
            if upr.file_serve_root_path is not None:
                return PlainTextResponse("wrong request type", status_code=400)
            dest_url = host + "/" + dest.lstrip("/")
            return await frp.proxy_pass_websocket(websocket, dest_url)
        except:
            return PlainTextResponse("no match", status_code=404)

    task = asyncio.create_task(app.sm.reload_loop())
    try:
        yield
    finally:
        task.cancel()


async def post_init(app: FastAPI):
    await app.sm.load_from()
    if EXPOSE_SERVICE_MANAGER:
        router = APIRouter(prefix=f"{SERVICE_MANAGER_API}")

        @router.get("/index.html")
        async def get_management_interface():
            try:
                with open("index.html", "r", encoding="utf-8") as f:
                    return PlainTextResponse(f.read(), media_type="text/html")
            except FileNotFoundError:
                return PlainTextResponse(
                    "Management interface not found", status_code=404
                )

        @router.get("/rules")
        async def rules_list():
            return app.sm.list()

        @router.delete("/rules/{name}")
        async def rules_delete(name: str):
            return await app.sm.delete(name)

        @router.put("/rules")
        async def rules_update(upr: UrlProxyRule):
            return await app.sm.add(upr)

        @router.post("/rules")
        async def rules_add(upr: UrlProxyRule):
            return await app.sm.add(upr, update=False)

        @router.post("/rules/match")
        async def rules_match(path_request: PathRequest):
            return app.sm.match(path_request.path)

        @router.post("/rules/{name}/preview")
        async def rules_preview(name: str, path: str):
            return app.sm.get(name).dest(path)

        @router.post("/rules/try")
        async def rules_try(upr_try_request: UprTryRequest):
            dest = upr_try_request.upr.dest(upr_try_request.path)
            return {
                "match": upr_try_request.upr.match(upr_try_request.path),
                "dest": dest,
                "host": upr_try_request.upr.host(upr_try_request.host),
                "file": (
                    os.path.join(upr_try_request.upr.file_serve_root_path, dest)
                    if upr_try_request.upr.file_serve_root_path is not None
                    else None
                ),
            }

        app.include_router(router)


app = FastAPI(lifespan=lifespan)
