from __future__ import annotations
import requests
import io
import argparse
import json
import sys
from typing import Literal, get_type_hints, Any
import os

PROCESS_MANAGER_URL = os.getenv("PROCESS_MANAGER_URL", "http://127.0.0.1:8000")
RULE_MANAGER_URL = os.getenv("RULE_MANAGER_URL", "http://127.0.0.1:8001/smgr")


class process:
    class algorithms:
        def get() -> dict:
            return requests.get(f"{PROCESS_MANAGER_URL}/algorithms").json()

        def info(id_or_prefix: str) -> dict:
            return requests.get(
                f"{PROCESS_MANAGER_URL}/algorithms/{id_or_prefix}"
            ).json()

        def upload(
            f: io.BufferedReader,
            version: str = "",
            description: str = "",
            auto_unpack_topdir: bool = False,
        ):
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
            if path is None:
                return __class__.info(id_or_prefix)
            return requests.post(
                f"{PROCESS_MANAGER_URL}/algorithms/{id_or_prefix}/cat",
                json={"path": path},
            ).text.replace("\r\n", "\n")

    class templates:
        def get() -> dict:
            return requests.get(f"{PROCESS_MANAGER_URL}/templates").json()

        def info(id_or_prefix: str) -> dict:
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
        def get() -> dict:
            return requests.get(f"{PROCESS_MANAGER_URL}/instances").json()

        def info(id_or_prefix: str) -> dict:
            return requests.get(
                f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}"
            ).json()

        def create(
            template_id_or_prefix: str, id: str = None, entry: str = None
        ) -> dict:
            return requests.post(
                f"{PROCESS_MANAGER_URL}/instances",
                json={
                    "template_id": template_id_or_prefix,
                    "id": id,
                    "entry": entry,
                },
            ).json()

        def stop(id_or_prefix: str) -> dict:
            return requests.post(
                f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/stop",
                json={"force": False},
            ).json()

        def delete(id_or_prefix: str) -> dict:
            return requests.delete(
                f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}"
            ).json()

        class logs:
            def out(id_or_prefix: str) -> str:
                return requests.get(
                    f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/logs/out"
                ).json()

            def err(id_or_prefix: str) -> str:
                return requests.get(
                    f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/logs/err"
                ).json()


class service:
    def get() -> dict:
        return requests.get(f"{RULE_MANAGER_URL}/rules").json()

    def delete(name: str):
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
        return requests.post(
            f"{RULE_MANAGER_URL}/rules/match",
            json={"path": path},
        ).json()

    def preview(name: str, path: str):
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


def _build_parser_recursive(
    parent_parser: argparse._SubParsersAction, current_class: Any, path: list[str]
) -> None:
    for attr_name in dir(current_class):
        if attr_name.startswith("_"):
            continue

        attr = getattr(current_class, attr_name)

        if isinstance(attr, type):
            subparser = parent_parser.add_parser(
                attr_name, help=f"{'.'.join(path + [attr_name])} operations"
            )
            new_parent = subparser.add_subparsers(
                dest="command_path", required=True, help="subcommand"
            )
            _build_parser_recursive(new_parent, attr, path + [attr_name])

        elif callable(attr):
            parser_cmd = parent_parser.add_parser(
                attr_name, help=f"{'.'.join(path + [attr_name])}"
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

                if param_type == bool:
                    if default is None or default is False:
                        parser_cmd.add_argument(
                            f"--{param}",
                            action="store_true",
                            default=default if default is not None else False,
                        )
                    else:
                        parser_cmd.add_argument(
                            f"--no-{param}",
                            dest=param,
                            action="store_false",
                            default=default,
                        )
                elif param_type == list[int] or param_type == list[dict]:
                    arg_kwargs = {
                        "nargs": "*",
                        "type": int if param_type == list[int] else json.loads,
                        "default": default if default is not None else [],
                        "help": f"{param} ({param_type.__name__})",
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
                        "help": f"{param} ({param_type})",
                    }
                    if not is_required:
                        arg_kwargs["required"] = False
                    parser_cmd.add_argument(f"--{param}", **arg_kwargs)
                elif param_type == io.BufferedReader:
                    parser_cmd.add_argument(
                        param, type=argparse.FileType("rb"), help="input file"
                    )
                else:
                    arg_name = f"--{param}" if not is_required else param
                    arg_kwargs = {
                        "type": _get_type_converter(param_type),
                        "default": default,
                        "help": f"{param}",
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
