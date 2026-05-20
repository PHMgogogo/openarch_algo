from __future__ import annotations
import requests
import io
import argparse
import json
import sys
from typing import Literal, get_type_hints, Any
import os
import time
import uuid

PROCESS_MANAGER_URL = os.getenv("PROCESS_MANAGER_URL", "http://127.0.0.1:8001/pmgr")
SERVICE_MANAGER_URL = os.getenv("SERVICE_MANAGER_URL", "http://127.0.0.1:8001/smgr")
SERVICE_ROOT_URL = os.getenv("SERVICE_ROOT_URL", "http://127.0.0.1:8001")


def auto(response: requests.Response):
    content_type = response.headers.get("Content-Type", "")
    if "application/json" not in content_type.lower():
        return response.text
        # return {"data": response.text, "msg": "response type is text"}
    return response.json()


class process:
    """Process manager operations for managing algorithms, templates and instances"""

    class algorithms:
        """Algorithm management operations"""

        @staticmethod
        def get() -> dict:
            """Get list of all algorithms

            Returns:
                dict: List of all algorithms
            """
            return auto(requests.get(f"{PROCESS_MANAGER_URL}/algorithms"))

        @staticmethod
        def info(id_or_prefix: str) -> dict:
            """Get information about a specific algorithm

            Args:
                id_or_prefix: Algorithm ID or prefix to search
            """
            return auto(
                requests.get(f"{PROCESS_MANAGER_URL}/algorithms/{id_or_prefix}")
            )

        @staticmethod
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
            return auto(
                requests.post(
                    f"{PROCESS_MANAGER_URL}/algorithms/upload",
                    files={"file": f},
                    data={
                        "version": version,
                        "description": description,
                        "auto_unpack_topdir": auto_unpack_topdir,
                    },
                )
            )

        @staticmethod
        def cat(
            id_or_prefix: str,
            path: str = None,
            offset: int = 0,
            length: int = 1024,
            encoding: Literal["b64img"] | str = "utf-8",
            fmt: str = None,
        ):
            """Show content of a file within an algorithm

            Args:
                id_or_prefix: Algorithm ID or prefix
                path: Path to file inside algorithm, show info if None
                offset: Start reading from this byte position
                length: Number of bytes to read, -1 for entire file
                encoding: Encoding for text content, use "b64img" for image to base64 conversion
                fmt: Output format for image conversion: jpg,jpeg,png,gif,webp,bmp,tiff,tif,ico,dib,icns,sgi,j2c,j2k,jp2,jpc,jpf,jpx
            """
            if path is None:
                return __class__.info(id_or_prefix)
            return auto(
                requests.post(
                    f"{PROCESS_MANAGER_URL}/algorithms/{id_or_prefix}/cat",
                    json={
                        "path": path,
                        "offset": offset,
                        "length": length,
                        "encoding": encoding,
                        "fmt": fmt,
                    },
                )
            )

    class templates:
        """Template management operations"""

        @staticmethod
        def get() -> dict:
            """Get list of all templates"""
            return auto(requests.get(f"{PROCESS_MANAGER_URL}/templates"))

        @staticmethod
        def info(id_or_prefix: str) -> dict:
            """Get information about a specific template

            Args:
                id_or_prefix: Template ID or prefix
            """
            return auto(requests.get(f"{PROCESS_MANAGER_URL}/templates/{id_or_prefix}"))

        @staticmethod
        def create(
            algorithm_id_or_prefix: str,
            id: str = None,
            entry: str = "python main.py",
            restart_always: bool = False,
            is_temporary: bool = False,
            volume: bool = False,
            restart_interval_seconds: float = 10,
            bind_listener: bool = False,
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
                bind_listener: Always bind proxy to first LISTEN port
                rules: List of environment rules
            """
            return auto(
                requests.post(
                    f"{PROCESS_MANAGER_URL}/templates",
                    json={
                        "algorithm": {"id": algorithm_id_or_prefix},
                        "id": id,
                        "entry": entry,
                        "restart_always": restart_always,
                        "is_temporary": is_temporary,
                        "volume": volume,
                        "restart_interval_seconds": restart_interval_seconds,
                        "bind_listener": bind_listener,
                        "rules": rules,
                    },
                )
            )

        @staticmethod
        def delete(id_or_prefix: str) -> dict:
            return auto(
                requests.delete(f"{PROCESS_MANAGER_URL}/templates/{id_or_prefix}")
            )

    class instances:
        """Running instance management operations"""

        @staticmethod
        def get() -> dict:
            """Get list of all running instances"""
            return auto(requests.get(f"{PROCESS_MANAGER_URL}/instances"))

        @staticmethod
        def info(id_or_prefix: str) -> dict:
            """Get information about a specific instance

            Args:
                id_or_prefix: Instance ID or prefix
            """
            return auto(requests.get(f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}"))

        @staticmethod
        def create(
            template_id_or_prefix: str, id: str = None, entry: str = None
        ) -> dict:
            """Create and start a new instance from template

            Args:
                template_id_or_prefix: Template ID or prefix to use
                id: Instance ID (generated automatically if not provided)
                entry: Override the entry command from template
            """
            return auto(
                requests.post(
                    f"{PROCESS_MANAGER_URL}/instances",
                    json={
                        "template_id": template_id_or_prefix,
                        "id": id,
                        "entry": entry,
                    },
                )
            )

        @staticmethod
        def cat(
            id_or_prefix: str,
            path: str = None,
            offset: int = 0,
            length: int = 1024,
            encoding: Literal["b64img"] | str = "utf-8",
            fmt: str = None,
        ):
            """Show content of a file within an instance

            Args:
                id_or_prefix: Instance ID or prefix
                path: Path to file inside instance, show info if None
                offset: Start reading from this byte position
                length: Number of bytes to read, -1 for entire file
                encoding: Encoding for text content, use "b64img" for image to base64 conversion
                fmt: Output format for image conversion: jpg,jpeg,png,gif,webp,bmp,tiff,tif,ico,dib,icns,sgi,j2c,j2k,jp2,jpc,jpf,jpx
            """
            if path is None:
                return __class__.info(id_or_prefix)
            return auto(
                requests.post(
                    f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/cat",
                    json={
                        "path": path,
                        "offset": offset,
                        "length": length,
                        "encoding": encoding,
                        "fmt": fmt,
                    },
                )
            )

        @staticmethod
        def stop(id_or_prefix: str) -> dict:
            """Stop a running instance

            Args:
                id_or_prefix: Instance ID or prefix to stop
            """
            return auto(
                requests.post(
                    f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/stop",
                    json={"force": False},
                )
            )

        @staticmethod
        def delete(id_or_prefix: str) -> dict:
            """Delete a stopped instance

            Args:
                id_or_prefix: Instance ID or prefix to delete
            """
            return auto(
                requests.delete(f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}")
            )

        @staticmethod
        def connections(id_or_prefix: str) -> dict:
            """Get connection information for a specific instance

            Args:
                id_or_prefix: Instance ID or prefix
            """
            return auto(
                requests.get(
                    f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/connections"
                )
            )

        class logs:
            """Log access operations"""

            @staticmethod
            def out(id_or_prefix: str) -> str:
                """Get stdout from instance

                Args:
                    id_or_prefix: Instance ID or prefix
                """
                return auto(
                    requests.get(
                        f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/logs/out"
                    )
                )

            @staticmethod
            def err(id_or_prefix: str) -> str:
                """Get stderr from instance

                Args:
                    id_or_prefix: Instance ID or prefix
                """
                return auto(
                    requests.get(
                        f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}/logs/err"
                    )
                )


class service:
    """Rule/service manager operations for routing rules"""

    @staticmethod
    def get() -> dict:
        """Get list of all routing rules"""
        return auto(requests.get(f"{SERVICE_MANAGER_URL}/rules"))

    @staticmethod
    def delete(name: str):
        """Delete a routing rule by name

        Args:
            name: Name of the rule to delete
        """
        return auto(requests.delete(f"{SERVICE_MANAGER_URL}/rules/{name}"))

    @staticmethod
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
        return auto(
            requests.put(
                f"{SERVICE_MANAGER_URL}/rules",
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
            )
        )

    @staticmethod
    def add(
        name: str,
        order: int = -1,
        rule_type: Literal["EXACT", "PREFIX", "REGEX"] = "EXACT",
        pattern: str = "",
        dest_index: list[int] = [],
        dest_format: str = "",
        rewrite_host: str = None,
        editable: bool = True,
        timeout: float = None,
        enable: bool = True,
        file_serve_root_path: str = None,
        default_entrance: str = None,
    ):
        """Add or update a routing rule

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
        return auto(
            requests.put(
                f"{SERVICE_MANAGER_URL}/rules",
                json={
                    "name": name,
                    "order": order,
                    "rule_type": rule_type,
                    "pattern": pattern,
                    "dest_index": dest_index,
                    "dest_format": dest_format,
                    "rewrite_host": rewrite_host,
                    "editable": editable,
                    "timeout": timeout,
                    "enable": enable,
                    "file_serve_root_path": file_serve_root_path,
                    "default_entrance": default_entrance,
                },
            )
        )

    @staticmethod
    def match(path: str):
        """Match a path against existing rules

        Args:
            path: Path to match (e.g. /api/foo)
        """
        return auto(
            requests.post(
                f"{SERVICE_MANAGER_URL}/rules/match",
                json={"path": path},
            )
        )

    @staticmethod
    def preview(name: str, path: str):
        """Preview how a rule matches a given path

        Args:
            name: Name of the rule to test
            path: Path to match against
        """
        return auto(
            requests.post(
                f"{SERVICE_MANAGER_URL}/rules/{name}/preview",
                json={"path": path},
            )
        )

    @staticmethod
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
        return auto(
            requests.post(
                f"{SERVICE_MANAGER_URL}/rules/test",
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
            )
        )


class highlevel:
    @staticmethod
    def create() -> dict:
        uid = str(uuid.uuid4())
        template = process.templates.info("framework")
        template["is_temporary"] = True
        template["id"] = uid
        template.setdefault("rules", []).append(
            {
                "name": uid,
                "order": -1,
                "rule_type": "PREFIX",
                "pattern": f"/{uid}",
                "dest_index": [1],
                "dest_format": "/%s",
                "rewrite_host": "127.0.0.1:0",
                "default_entrance": f"/{uid}/?prefix={uid}",
            }
        )
        entry = template["entry"] + f" --root-path /{uid}"
        r = process.templates.create(
            template["algorithm"]["id"],
            template["id"],
            entry,
            template["restart_always"],
            template["is_temporary"],
            template["volume"],
            template["restart_interval_seconds"],
            template["bind_listener"],
            template["rules"],
        )
        # print(r)
        process.instances.create(uid, uid, entry)
        result = {
            "instance_id": uid,
            "entrance": f"{SERVICE_ROOT_URL}/{uid}/openapi.json",
            "base_url": f"{SERVICE_ROOT_URL}/{uid}",
            "doc_url": f"{SERVICE_ROOT_URL}/{uid}/docs",
            "index_url": f"{SERVICE_ROOT_URL}/{uid}/?prefix={uid}",
            "help": (
                "Algorithm service is now online. "
                "POST {base_url}/load to load a model, "
                "GET {base_url}/openapi.json to learn about other interfaces."
            ),
        }
        return result

    def delete(instance_id: str) -> dict:
        return process.instances.delete(instance_id)


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
