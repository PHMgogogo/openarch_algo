from enum import Enum, auto
from pydantic import BaseModel, Field
import uuid
import re
class RuleType(str, Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name
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