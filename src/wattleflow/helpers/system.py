# Module name: system.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module defines system-level classes and utilities for managing paths,
loading classes dynamically, executing shell commands, and handling file
operations within the Wattleflow framework. It provides robust mechanisms
for runtime class loading, project structure detection, temporary path
management, and process execution with integrated audit logging.
"""


import os
import platform
import subprocess
import functools
import inspect
import shutil
import shlex

from abc import ABC
from importlib import import_module
from logging import NOTSET, Handler, getLogger
from os import PathLike
from pathlib import Path
from tempfile import gettempdir
from typing import Sequence, Mapping, Union

try:  # Python 3.8+
    from typing import final, Optional
except Exception:  # Python 3.7 fallback
    from typing_extensions import final, Optional  # type: ignore

from wattleflow.core import IWattleflow
from wattleflow.concrete.logger import AuditLogger
from wattleflow.constants import Event
from wattleflow.constants.keys import KEY_CONFIG_FILE_NAME
from wattleflow.helpers.normaliser import Normaliser


class ClassLoader(IWattleflow, ABC):  # type: ignore
    """
    Dynamic class loader with audit logging.
    """

    def __init__(
        self,
        class_path: str,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        *args,
        **kwargs,
    ):

        IWattleflow.__init__(self)

        self._logger = getLogger(f"[{self.__class__.__name__}]")
        self._logger.setLevel(level)
        self.log = AuditLogger(level=level, logger=self._logger, handler=handler)

        self.log.debug(
            msg=Event.Constructor.value,
            class_path=class_path,
            level=level,
            handler=handler,
            *args,
            **kwargs,
        )

        try:
            module_path, class_name = class_path.rsplit(".", 1)
        except ValueError as e:
            self.log.error(
                msg=Event.Constructor.value,
                reason=str(e),
                class_path=class_path,
                error=e,
            )
            raise ValueError(f"Invalid class path: {class_path}") from e

        self.log.debug(
            msg=Event.Constructor.value,
            module_path=module_path,
            class_name=class_name,
        )

        try:
            module = import_module(module_path)
        except ModuleNotFoundError as e:
            self.log.error(
                msg="Module not found",
                reason=str(e),
                module_path=module_path,
                error=e,
            )
            raise

        cls = getattr(module, class_name)
        self.cls = cls
        try:
            self.instance = cls(*args, **kwargs)
        except Exception as e:
            self.log.error(
                msg="Class instantiation failed",
                cls=cls,
                error=e,
                reason=str(e),
            )
            raise

        self.log.debug(
            msg=Event.Constructor.value,
            status="Class loaded",
            cls=cls.__name__,
        )

        # if not hasattr(module, class_name):
        #     error = f"Class {class_name} not found in module {module_path}"
        #     self.error(
        #         msg=Event.Constructor.value,
        #         reason=error,
        #         class_name=class_name,
        #         module=module,
        #     )
        #     raise AttributeError(error)

        # self.cls = getattr(module, class_name)
        # self.instance = self.cls(*args, **kwargs)
        # self.debug(msg=Event.Constructor.value, status="Class loaded", cls=self.cls)


Command = Union[str, Sequence[str]]
Pathish = Union[str, PathLike[str], Path]


def check_path(path: Pathish, raise_error: bool = True) -> bool:
    if path is None:
        if raise_error:
            raise FileNotFoundError("Path must be assigned!")
        return False

    p = Path(path)
    if not p.exists():
        if raise_error:
            raise FileNotFoundError(f"Path not found: {p}")
        return False
    return True


def decorator(*dargs, **dkwargs):
    if dargs and callable(dargs[0]) and not dkwargs:
        fn = dargs[0]

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return Proxy(fn)(*args, **kwargs)

        return wrapper

    before_call = dkwargs.get("before_call")
    after_call = dkwargs.get("after_call")

    def _outer(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return Proxy(fn, before_call=before_call, after_call=after_call)(
                *args, **kwargs
            )

        return wrapper

    return _outer


@final
class FileStorage:
    def __init__(
        self, repository_path: str, filename: str, create: bool, normalised=False
    ):
        self.origin = Path(filename)
        self.path = Path(repository_path)

        if (
            not os.path.isdir(self.path)  # noqa: W503
            and not os.access(self.path, os.R_OK)  # noqa: W503
            and not create  # noqa: W503
        ):
            raise FileNotFoundError(
                f"Path doesn't exist or not accessible: {str(self.path)}"
            )

        if create and self.path.exists() is False:
            self.path.mkdir(parents=True, exist_ok=True)

        name = (
            Normaliser.transform(self.origin.name) if normalised else self.origin.name
        )

        self.filename = self.path.joinpath(name).with_suffix(self.origin.suffix)

    @property
    def size(self) -> int:
        return os.stat(self.origin.absolute()).st_size

    def with_suffix(self, suffix: str) -> Path:
        return self.filename.with_suffix(suffix)

    def with_dir(self, directory=None, mkdir=True) -> Path:
        dir = directory if directory else self.filename.stem
        out_dir = self.path.joinpath(dir)
        if mkdir:
            out_dir.mkdir(parents=True, exist_ok=True)

        return out_dir.joinpath(self.filename.name)


@final
class Project:
    def __init__(
        self,
        file_path: Pathish,
        root_marker: Pathish,
        config_name: str = KEY_CONFIG_FILE_NAME,
    ):
        p = Path(file_path).resolve()
        marker_parts = Path(root_marker).parts

        found: Optional[Path] = None
        for parent in [p] + list(p.parents):
            parts = parent.parts
            for i in range(0, len(parts) - len(marker_parts) + 1):
                if (
                    tuple(parts[i : i + len(marker_parts)]) == marker_parts
                ):  # noqa: E203
                    found = Path(*parts[: i + len(marker_parts)])
                    break
            if found:
                break

        root_path = found or p.parent
        if not root_path.exists():
            raise FileNotFoundError(f"Project [{root_path}] path is not found.")

        self._root: str = str(root_path)
        self._config: str = str(root_path / config_name)

    @property
    def root(self) -> str:
        return self._root

    @property
    def config(self) -> str:
        return self._config


@final
class Proxy:
    def __init__(self, target_method, before_call=None, after_call=None):
        self.target_method = target_method
        self.before_call = before_call
        self.after_call = after_call
        self._is_async = inspect.iscoroutinefunction(target_method)

    def _call_after(self, result, *args, **kwargs):
        if not self.after_call:
            return
        try:
            params = inspect.signature(self.after_call).parameters
            if len(params) == 1:
                return self.after_call(result)
            return self.after_call(result, *args, **kwargs)
        except Exception:
            # ne ruši cilj; po želji: re-raise
            return

    def __call__(self, *args, **kwargs):
        if self._is_async:

            async def _runner():
                if self.before_call:
                    self.before_call(*args, **kwargs)
                res = await self.target_method(*args, **kwargs)
                self._call_after(res, *args, **kwargs)
                return res

            return _runner()
        else:
            if self.before_call:
                self.before_call(*args, **kwargs)
            res = self.target_method(*args, **kwargs)
            self._call_after(res, *args, **kwargs)
            return res


@final
class ShellExecutor:
    def __init__(self):
        self.os_name = platform.system().lower()
        self.shell = self.detect_shell()

    def detect_shell(self) -> str:
        if self.os_name == "windows":
            return "powershell" if self.is_powershell_available() else "cmd"
        return os.environ.get("SHELL", "bash").split(os.sep)[-1]

    def is_powershell_available(self) -> bool:
        return shutil.which("powershell") is not None

    def execute(
        self,
        command: Command,
        shell: Optional[str] = None,
        *,
        use_shell: bool = False,
        timeout: Optional[int] = None,
        cwd: Optional[Pathish] = None,
        env: Optional[Mapping[str, str]] = None,
    ):

        shell = shell or self.shell

        if isinstance(command, str) and not use_shell:
            cmd_list: Sequence[str] = shlex.split(command)
            # run_kwargs = dict(shell=False)
        elif isinstance(command, (list, tuple)):
            cmd_list = list(command)
            # run_kwargs = dict(shell=False)
        else:
            # eksplicitni shell (potreban za pipe/redirect)
            if shell == "cmd":
                cmd_list = ["cmd", "/c", command]  # type: ignore[arg-type]
            elif shell == "powershell":
                cmd_list = [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,  # type: ignore
                ]  # type: ignore[arg-type]
            else:
                cmd_list = ["bash", "-c", command]  # type: ignore[arg-type]
            # run_kwargs = dict(shell=False)

        try:
            # result = subprocess.run(cmd_list, text=True, capture_output=True, check=True)
            result = subprocess.run(
                args=cmd_list,
                text=True,
                capture_output=True,
                check=True,
                timeout=timeout,
                cwd=str(cwd) if cwd else None,
                env=env,
                shell=False,
                # **run_kwargs,
            )
            to_s = lambda x: (x or "").strip()
            return {
                "stdout": to_s(result.stdout),
                "stderr": to_s(result.stderr),
                "returncode": result.returncode,
            }
        except subprocess.CalledProcessError as e:
            to_s = lambda x: (x or "").strip()
            return {
                "stdout": to_s(e.stdout),
                "stderr": to_s(e.stderr),
                "returncode": e.returncode,
            }
        except FileNotFoundError:
            return {
                "stdout": "",
                "stderr": f"Command or shell not found: {cmd_list[0]}",
                "returncode": 127,
            }
        except subprocess.TimeoutExpired as e:
            return {
                "stdout": (e.stdout or "").strip(),
                "stderr": f"Timeout after {timeout}s",
                "returncode": 124,
            }


@final
class TempPathHelper:
    def __init__(self, file_path: Optional[str], create_dir=True):

        if (not file_path) or (file_path.strip() == ""):
            raise ValueError(f"{file_path} must be assigned in yaml config.")

        if file_path.startswith("TEMP"):
            file_path = file_path.replace("TEMP", gettempdir())

        self.source_path: Path = Path(file_path)

        if not (self.source_path.exists()) and (create_dir is True):
            self.source_path.mkdir(parents=True)

    @property
    def full_path(self) -> Path:
        return self.source_path.absolute()
