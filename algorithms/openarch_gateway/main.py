import fastapi_reverse_proxy as frp
from enum import Enum, auto
import re
from fastapi import Request, WebSocket, FastAPI, APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, field_serializer
import uuid
import json
import os
from contextlib import asynccontextmanager
from filelock import AsyncFileLock, FileLock
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
EXPOSE_PROXY_MANAGER = get_bool_env_strict(
    os.environ.get("EXPOSE_PROXY_MANAGER", "true")
)
PROXY_MANAGER_API = os.environ.get("PROXY_MANAGER_API", "/pmgr")
# proxy_lock = AsyncFileLock(PROXY_LOCK_PATH)
proxy_lock = FileLock(PROXY_LOCK_PATH)


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

    @field_serializer("pattern")
    def _serialize_pattern(self, value):
        if isinstance(value, re.Pattern):
            return value.pattern
        return value


class PathRequest(BaseModel):
    path: str


class UprTryRequest(BaseModel):
    path: str
    upr: UrlProxyRule
    host: str

class ProxyManager:
    _rules: dict[str, UrlProxyRule]
    _sorted_rules: list[UrlProxyRule]

    def __init__(self):
        self._rules = dict[str, UrlProxyRule]()
        self._sorted_rules = list[UrlProxyRule]()
        # await self.load_from()

    async def save_to(self, path: str = PROXY_RULE_PATH):
        with proxy_lock:
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
        with proxy_lock:
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
        with proxy_lock:
            await self.load_from()
            if upr.name in self._rules:
                if not self._rules[upr.name].editable:
                    return
            self._rules[upr.name] = upr
            await self.flush()

    async def delete(self, name: str) -> None:
        with proxy_lock:
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


pm = ProxyManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await post_init(app)

    @app.api_route("{path:path}",methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    async def gateway(request: Request, path: str):
        try:
            upr, dest = pm.match(path)
            raw_host = request.headers.get("host")
            host = upr.host(raw_host)
            if host == raw_host:
                return PlainTextResponse("loop", status_code=508)
            print(host)
            return await frp.proxy_pass(request, host, dest, upr.timeout)
        except:
            return PlainTextResponse("no match", status_code=404)

    @app.websocket("{path:path}")
    async def ws_gateway(websocket: WebSocket, path: str):
        try:
            upr, dest = pm.match(path)
            raw_host = websocket.headers.get("host")
            host = upr.host(raw_host)
            if host == raw_host:
                return PlainTextResponse("loop", status_code=508)
            dest_url = host + "/" + dest.lstrip("/")
            return await frp.proxy_pass_websocket(websocket, dest_url)
        except:
            return PlainTextResponse("no match", status_code=404)

    task = asyncio.create_task(pm.reload_loop())
    try:
        yield
    finally:
        task.cancel()


async def post_init(app: FastAPI):
    await pm.load_from()
    await pm.add(
        UrlProxyRule(
            name="default",
            pattern="",
            dest_format="/docs",
            dest_index=[],
            rule_type=RuleType.PREFIX,
            editable=False,
        )
    )

    if not EXPOSE_PROXY_MANAGER:
        await pm.delete("pmgr")
    if EXPOSE_PROXY_MANAGER:
        await pm.add(
            UrlProxyRule(
                name="pmgr",
                pattern="/pmgr",
                dest_format="/pmgr%s",
                dest_index=[1],
                rule_type=RuleType.PREFIX,
                editable=False,
                order=1,
            )
        )
        router = APIRouter(prefix=f"{PROXY_MANAGER_API}")

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
            return pm.list()

        @router.delete("/rules/{name}")
        async def rules_delete(name: str):
            return await pm.delete(name)

        @router.put("/rules")
        async def rules_update(upr: UrlProxyRule):
            return await pm.add(upr)

        @router.post("/rules")
        async def rules_add(upr: UrlProxyRule):
            return await pm.add(upr, update=False)

        @router.post("/rules/match")
        async def rules_match(path_request: PathRequest):
            return pm.match(path_request.path)

        @router.post("/rules/{name}/preview")
        async def rules_preview(name: str, path: str):
            return pm.get(name).dest(path)

        @router.post("/rules/try")
        async def rules_try(upr_try_request: UprTryRequest):
            return {
                "match":upr_try_request.upr.match(upr_try_request.path),
                "dest":upr_try_request.upr.dest(upr_try_request.path),
                "host":upr_try_request.upr.host(upr_try_request.host),
            }

        app.include_router(router)


app = FastAPI(lifespan=lifespan)
