from proxy.http.proxy import HttpProxyBasePlugin
from typing import Any
from enum import Enum, auto
import re


class RuleType(Enum):
    EXACT = auto()
    PREFIX = auto()
    REGEX = auto()


class UrlProxyRule:
    order: int = -1
    rule_type: RuleType
    pattern: str | re.Pattern
    dest_index: list[int] = None
    dest_format: str = None
    rewrite_host: str = None

    def __init__(
        self,
        pattern: str,
        rule_type: RuleType = RuleType.EXACT,
        order: int = -1,
        dest_index: list[int] = None,
        dest_format: str = None,
        rewrite_host: str = None,
    ):
        self.order = order
        self.rule_type = rule_type
        self.pattern = pattern
        if self.rule_type == RuleType.REGEX:
            self.pattern = re.compile(pattern)
        if dest_index is None and self.rule_type == RuleType.EXACT:
            self.dest_index = [0]
        if dest_index is None and self.rule_type == RuleType.PREFIX:
            self.dest_index = [1]
        if dest_index is None and self.rule_type == RuleType.REGEX:
            self.dest_index = [0]
        if dest_format is None and self.rule_type == RuleType.EXACT:
            self.dest_format = "%s"
        if dest_format is None and self.rule_type == RuleType.PREFIX:
            self.dest_format = "%s"
        if dest_format is None and self.rule_type == RuleType.REGEX:
            self.dest_format = "%s"
        self.rewrite_host = rewrite_host

    def dest(self, path: str) -> str:
        result, groups = self.match(path)
        if not result:
            return ""
        else:
            tuples = tuple(groups[idx] for idx in self.dest_index)
            return self.dest_format % tuples
    
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
        result = re.fullmatch(self.pattern, path)
        if result:
            return True, list(result.groups())
        return False, []


class DynamicProxyPlugin(HttpProxyBasePlugin):
    config: dict[str, Any]

    def before_upstream_connection(self, request):
        host = request.host.decode()

        # request.
    def handle_client_request(self,request):
        request.headers[b"X-Dynamic-Proxy"] = b"Enabled"
        return request

if __name__ == "__main__":
    upr = UrlProxyRule("/backend", RuleType.PREFIX)
    print(upr.dest("/backend/api"))
