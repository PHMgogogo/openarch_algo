import requests
import io
from typing import Literal
import os

PROCESS_MANAGER_URL = os.getenv("PROCESS_MANAGER_URL", "http://localhost:8000")
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
                f"{PROCESS_MANAGER_URL}/algorithms",
                files={"file": f},
                data={
                    "version": version,
                    "description": description,
                    "auto_unpack_topdir": auto_unpack_topdir,
                },
            ).json()

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
                f"{PROCESS_MANAGER_URL}/instances/stop",
                json={"id": id_or_prefix},
            ).json()

        def delete(id_or_prefix: str) -> dict:
            return requests.delete(
                f"{PROCESS_MANAGER_URL}/instances/{id_or_prefix}"
            ).json()

        class logs:
            def out(id_or_prefix: str) -> str:
                return requests.get(
                    f"{PROCESS_MANAGER_URL}/instances/logs/{id_or_prefix}"
                ).text

            def err(id_or_prefix: str) -> str:
                return requests.get(
                    f"{PROCESS_MANAGER_URL}/instances/logs/{id_or_prefix}/err"
                ).text


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

    def try_(
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
            f"{RULE_MANAGER_URL}/rules/try",
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
