from __future__ import annotations
import requests
import io
import argparse
import json
import sys
from typing import Literal, get_type_hints, Any
import os

PROCESS_MANAGER_URL = os.getenv("PROCESS_MANAGER_URL", "http://127.0.0.1:8001/pmgr")
RULE_MANAGER_URL = os.getenv("RULE_MANAGER_URL", "http://127.0.0.1:8001/smgr")


class process:
    """Process manager operations for managing algorithms, templates and instances"""

    class algorithms:
        """Algorithm management operations"""

        def get() -> dict:
            """Get list of all algorithms

            Returns:
                dict: List of all algorithms
            """
            return requests.get(f"{PROCESS_MANAGER_URL}/algorithms").json()

        def info(id_or_prefix: str) -> dict:
            """Get information about a specific algorithm

            Args:
                id_or_prefix: Algorithm ID or prefix to search
            """
            return requests.get(
                f"{PROCESS_MANAGER_URL}/algorithms/{id_or_prefix}"
            ).json()

        def upload(
            f: io.BufferedReader,
            version: str = "",
            description: str = "",
            auto_unpack_topdir: bool = False,
        ):
            """Upload a new algorithm archive

            Args:
                f: Archive file to upload (zip/tar.gz/etc)
                version: Version string for this algorithm
                description: Description of the algorithm
                auto_unpack_topdir: Auto-unpack if archive contains single top directory
            """
            return requests.post(
                f"{PROCESS_MANAGER_URL}/algorithms/upload",
                files={"file": f},
                data={
                    "version": version,
                    "description": description,
                    "auto_unpack_topdir": auto_unpack_topdir,
                },
            ).json()

        def cat(id_or_prefix: str, path: str = None) -> str:
            """Show content of a file within an algorithm

            Args:
                id_or_prefix: Algorithm ID or prefix
                path: Path to file inside algorithm, show info if None
            """
            if path is None:
                return __class__.info(id_or_prefix)
            return requests.post(
                f"{PROCESS_MANAGER_URL}/algorithms/{id_or_prefix}/cat",
                json={"path": path},
            ).text.replace("\r\n", "\n")

    class templates:
        """Template management operations"""

        def get() -> dict:
            """Get list of all templates"""
            return requests.get(f"{PROCESS_MANAGER_URL}/templates").json()

        def info(id_or_prefix: str) -> dict:
            """Get information about a specific template

            Args:
                id_or_prefix: Template ID or prefix
            """
            return requests.get(
                f"{PROCESS_MANAGER_URL}/templates/{id_or_prefix}"
            ).json()

        def create(
            algorithm_id_or_prefix: str,
            id: str = None,
            entry: str = "python main.py",
            restart_always: bool = False,
            is_temporary: bool = False,
            volume: bool = False,
            restart_interval_seconds: float = 10,
            rules: list[dict[str, float | str | int | bool]] = [],
        ) -> dict:
            """Create a new template from an algorithm

            Args:
                algorithm_id_or_prefix: Source algorithm ID or prefix
                id: Template ID (generated automatically if not provided)
                entry: Command to run when starting the instance
                restart_always: Always restart when process exits
                is_temporary: Delete instance after it stops
                volume: Use persistent volume for this template
                restart_interval_seconds: Wait seconds before restart
                rules: List of environment rules
            """
            return requests.post(
                f"{PROCESS_MANAGER_URL}/templates",
                json={
                    "algorithm_id": algorithm_id_or_prefix,
                    "id": id,
                    "entry": entry,
                    "restart_always": restart_always,
                    "is_temporary": is_temporary,
                    "volume": volume,
                    "restart_interval_seconds": restart_interval_seconds,
                    "rules": rules,
                },
            ).json()

    class instances:
        """Running instance management operations"""

        def get() -> dict:
            """Get list of all running instances"""
            return requests.get(f"{PROCESS_MANAGER_URL}/instances").json()

        def info(id_or_prefix: str) -> dict:
            """Get information about a specific instance

            Args:
                id_or_prefix: Instance ID or prefix
            """
            return requests.get(
                f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}"
            ).json()

        def create(
            template_id_or_prefix: str, id: str = None, entry: str = None
        ) -> dict:
            """Create and start a new instance from template

            Args:
                template_id_or_prefix: Template ID or prefix to use
                id: Instance ID (generated automatically if not provided)
                entry: Override the entry command from template
            """
            return requests.post(
                f"{PROCESS_MANAGER_URL}/instances",
                json={
                    "template_id": template_id_or_prefix,
                    "id": id,
                    "entry": entry,
                },
            ).json()

        def stop(id_or_prefix: str) -> dict:
            """Stop a running instance

            Args:
                id_or_prefix: Instance ID or prefix to stop
            """
            return requests.post(
                f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/stop",
                json={"force": False},
            ).json()

        def delete(id_or_prefix: str) -> dict:
            """Delete a stopped instance

            Args:
                id_or_prefix: Instance ID or prefix to delete
            """
            return requests.delete(
                f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}"
            ).json()

        class logs:
            """Log access operations"""

            def out(id_or_prefix: str) -> str:
                """Get stdout from instance

                Args:
                    id_or_prefix: Instance ID or prefix
                """
                return requests.get(
                    f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/logs/out"
                ).json()

            def err(id_or_prefix: str) -> str:
                """Get stderr from instance

                Args:
                    id_or_prefix: Instance ID or prefix
                """
                return requests.get(
                    f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/logs/err"
                ).json()


class service:
    """Rule/service manager operations for routing rules"""

    def get() -> dict:
        """Get list of all routing rules"""
        return requests.get(f"{RULE_MANAGER_URL}/rules").json()

    def delete(name: str):
        """Delete a routing rule by name

        Args:
            name: Name of the rule to delete
        """
        return requests.delete(f"{RULE_MANAGER_URL}/rules/{name}").json()

    def update(
        name: str,
        order: int = -1,
        rule_type: Literal["EXACT", "PREFIX", "REGEX"] = "EXACT",
        pattern: str = "",
        dest_index: list[int] = [],
        rewrite_host: str = None,
        editable: bool = True,
        timeout: float = None,
        enable: bool = True,
        file_serve_root_path: str = None,
    ):
        """Update an existing routing rule

        Args:
            name: Name of the rule to update
            order: Rule matching order (lower matches first)
            rule_type: Matching type: EXACT, PREFIX, or REGEX
            pattern: Matching pattern string
            dest_index: Target backend indices
            rewrite_host: Rewrite Host header to this value
            editable: Allow UI editing of this rule
            timeout: Custom timeout for this route in seconds
            enable: Enable or disable this rule
            file_serve_root_path: Root path for static file serving
        """
        return requests.put(
            f"{RULE_MANAGER_URL}/rules",
            json={
                "name": name,
                "order": order,
                "rule_type": rule_type,
                "pattern": pattern,
                "dest_index": dest_index,
                "rewrite_host": rewrite_host,
                "editable": editable,
                "timeout": timeout,
                "enable": enable,
                "file_serve_root_path": file_serve_root_path,
            },
        ).json()

    def add(
        name: str,
        order: int = -1,
        rule_type: Literal["EXACT", "PREFIX", "REGEX"] = "EXACT",
        pattern: str = "",
        dest_index: list[int] = [],
        rewrite_host: str = None,
        editable: bool = True,
        timeout: float = None,
        enable: bool = True,
        file_serve_root_path: str = None,
    ):
        """Add a new routing rule

        Args:
            name: Name of the new rule
            order: Rule matching order (lower matches first)
            rule_type: Matching type: EXACT, PREFIX, or REGEX
            pattern: Matching pattern string
            dest_index: Target backend indices
            rewrite_host: Rewrite Host header to this value
            editable: Allow UI editing of this rule
            timeout: Custom timeout for this route in seconds
            enable: Enable or disable this rule
            file_serve_root_path: Root path for static file serving
        """
        return requests.post(
            f"{RULE_MANAGER_URL}/rules",
            json={
                "name": name,
                "order": order,
                "rule_type": rule_type,
                "pattern": pattern,
                "dest_index": dest_index,
                "rewrite_host": rewrite_host,
                "editable": editable,
                "timeout": timeout,
                "enable": enable,
                "file_serve_root_path": file_serve_root_path,
            },
        ).json()

    def match(path: str):
        """Match a path against existing rules

        Args:
            path: Path to match (e.g. /api/foo)
        """
        return requests.post(
            f"{RULE_MANAGER_URL}/rules/match",
            json={"path": path},
        ).json()

    def preview(name: str, path: str):
        """Preview how a rule matches a given path

        Args:
            name: Name of the rule to test
            path: Path to match against
        """
        return requests.post(
            f"{RULE_MANAGER_URL}/rules/{name}/preview",
            json={"path": path},
        ).json()

    def test(
        path: str,
        host: str,
        name: str,
        order: int = -1,
        rule_type: Literal["EXACT", "PREFIX", "REGEX"] = "EXACT",
        pattern: str = "",
        dest_index: list[int] = [],
        rewrite_host: str = None,
        editable: bool = True,
        timeout: float = None,
        enable: bool = True,
        file_serve_root_path: str = None,
    ):
        """Test a routing rule without adding it

        Args:
            path: Request path to test
            host: Request host
            name: Rule name for testing
            order: Rule matching order
            rule_type: Matching type: EXACT, PREFIX, or REGEX
            pattern: Matching pattern string
            dest_index: Target backend indices
            rewrite_host: Rewrite Host header to this value
            editable: Allow UI editing of this rule
            timeout: Custom timeout for this route in seconds
            enable: Enable or disable this rule
            file_serve_root_path: Root path for static file serving
        """
        return requests.post(
            f"{RULE_MANAGER_URL}/rules/test",
            json={
                "path": path,
                "host": host,
                "upr": {
                    "name": name,
                    "order": order,
                    "rule_type": rule_type,
                    "pattern": pattern,
                    "dest_index": dest_index,
                    "rewrite_host": rewrite_host,
                    "editable": editable,
                    "timeout": timeout,
                    "enable": enable,
                    "file_serve_root_path": file_serve_root_path,
                },
            },
        ).json()


def _parse_docstring(docstring: str) -> tuple[str, dict[str, str]]:
    if not docstring:
        return "", {}

    lines = [line.rstrip() for line in docstring.split("\n")]
    lines = [line for line in lines if line.strip()]

    description = []
    param_helps = {}
    in_args = False

    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith(
            ("args:", "parameters:", "params:", "returns:", "return:", "example:")
        ):
            in_args = stripped.startswith(("args:", "parameters:", "params:"))
            continue
        if in_args:
            parts = line.strip().split(":", 1)
            if len(parts) == 2:
                param_name = parts[0].strip()
                param_help = parts[1].strip()
                param_helps[param_name] = param_help
            continue
        if in_args and line.startswith((" ", "\t")):
            continue
        if not in_args:
            description.append(line.strip())

    return " ".join(description).strip(), param_helps


def _build_parser_recursive(
    parent_parser: argparse._SubParsersAction, current_class: Any, path: list[str]
) -> None:
    for attr_name in dir(current_class):
        if attr_name.startswith("_"):
            continue

        attr = getattr(current_class, attr_name)

        if isinstance(attr, type):
            class_doc = attr.__doc__ or ""
            class_help = (
                class_doc.strip().split("\n")[0]
                if class_doc
                else f"{'.'.join(path + [attr_name])} operations"
            )
            subparser = parent_parser.add_parser(
                attr_name,
                help=class_help,
                description=(attr.__doc__ or "").strip() or None,
            )
            new_parent = subparser.add_subparsers(
                dest="command_path", required=True, help="subcommand"
            )
            _build_parser_recursive(new_parent, attr, path + [attr_name])

        elif callable(attr):
            func_doc = attr.__doc__
            description, param_helps = _parse_docstring(func_doc)
            help_text = (
                description if description else f"{'.'.join(path + [attr_name])}"
            )
            parser_cmd = parent_parser.add_parser(
                attr_name, help=help_text, description=description or None
            )
            type_hints = get_type_hints(attr)
            defaults = attr.__defaults__ or ()

            params = list(attr.__code__.co_varnames[: attr.__code__.co_argcount])
            num_defaults = len(defaults)
            start_default_idx = len(params) - num_defaults

            for i, param in enumerate(params):
                is_required = i < start_default_idx
                default = defaults[i - start_default_idx] if not is_required else None
                param_type = type_hints.get(param, Any)
                param_help = param_helps.get(param, param)

                if param_type == bool:
                    if default is None or default is False:
                        parser_cmd.add_argument(
                            f"--{param}",
                            action="store_true",
                            default=default if default is not None else False,
                            help=param_help,
                        )
                    else:
                        parser_cmd.add_argument(
                            f"--no-{param}",
                            dest=param,
                            action="store_false",
                            default=default,
                            help=param_help,
                        )
                elif param_type == list[int] or param_type == list[dict]:
                    arg_kwargs = {
                        "nargs": "*",
                        "type": int if param_type == list[int] else json.loads,
                        "default": default if default is not None else [],
                        "help": f"{param_help} ({param_type.__name__})",
                    }
                    if not is_required:
                        arg_kwargs["required"] = False
                    parser_cmd.add_argument(f"--{param}", **arg_kwargs)
                elif (
                    hasattr(param_type, "__origin__") and param_type.__origin__ is list
                ):
                    arg_kwargs = {
                        "nargs": "*",
                        "default": default if default is not None else [],
                        "help": f"{param_help} ({param_type})",
                    }
                    if not is_required:
                        arg_kwargs["required"] = False
                    parser_cmd.add_argument(f"--{param}", **arg_kwargs)
                elif param_type == io.BufferedReader:
                    parser_cmd.add_argument(
                        param,
                        type=argparse.FileType("rb"),
                        help=param_help or "input file",
                    )
                else:
                    arg_name = f"--{param}" if not is_required else param
                    arg_kwargs = {
                        "type": _get_type_converter(param_type),
                        "default": default,
                        "help": param_help,
                    }
                    if not is_required:
                        arg_kwargs["required"] = False
                    parser_cmd.add_argument(arg_name, **arg_kwargs)

            parser_cmd.set_defaults(func=attr, command_path=path + [attr_name])


def _get_type_converter(type_hint):
    if type_hint == int:
        return int
    if type_hint == float:
        return float
    if type_hint == bool:
        return lambda x: x.lower() in ("true", "yes", "1", "y")
    return str


def _get_current_class(root_module, command_path: list[str]) -> Any:
    current = root_module
    for part in command_path:
        current = getattr(current, part)
    return current


def get_parser(prog: str = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog, description="OpenArch Algo API Command Line Client"
    )
    subparsers = parser.add_subparsers(
        dest="command_path", required=True, help="top level command"
    )

    current_module = sys.modules[__name__]
    for top_level_name in dir(current_module):
        if top_level_name.startswith("_"):
            continue
        obj = getattr(current_module, top_level_name)
        if isinstance(obj, type) and obj.__module__ == current_module.__name__:
            subparser = subparsers.add_parser(
                top_level_name, help=f"{top_level_name} operations"
            )
            new_subparsers = subparser.add_subparsers(
                dest="command_path", required=True, help="subcommand"
            )
            _build_parser_recursive(new_subparsers, obj, [top_level_name])
    return parser


def collect_all_help(parser: argparse.ArgumentParser) -> dict[str, str]:
    result = {}

    def recurse(p: argparse.ArgumentParser, path: list[str]):
        cmd = " ".join(path) if path else "root"
        result[cmd] = p.format_help()

        for action in p._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, subp in action._name_parser_map.items():
                    recurse(subp, path + [name])

    recurse(parser, [])
    return result


def doc(prog: str = None, parser: argparse.ArgumentParser = None) -> str:
    if parser is None:
        parser = get_parser(prog)
    results = []
    all_help = collect_all_help(parser)
    for cmd, help_text in all_help.items():
        results.append("-" * 2)
        results.append(help_text)
    return "\n".join(results)


def main():
    parser = get_parser()
    args = parser.parse_args()
    func_args = vars(args)
    func = func_args.pop("func")
    func_args.pop("command_path")
    result = func(**func_args)

    if isinstance(result, (dict, list)):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result)


if __name__ == "__main__":
    main()
