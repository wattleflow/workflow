# Module name: helpers/system.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module defines system-level classes and utilities for managing paths,
loading classes dynamically, executing shell commands, and handling file
operations within the Wattleflow framework. It provides robust mechanisms
for runtime class loading, project structure detection, temporary path
management, and process execution with integrated audit logging.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import functools
import inspect
import os
import platform
import shlex
import shutil
import subprocess

from importlib import import_module
from logging import NOTSET, Handler, getLogger
from os import PathLike
from pathlib import Path
from tempfile import gettempdir
from typing import Sequence, Mapping, Union, final, Optional

from wattleflow.core import IWattleflow
from wattleflow.constants.enums import Event
from wattleflow.constants.keys import KEY_CONFIG_FILE_NAME
from wattleflow.helpers.normaliser import Normaliser

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Types                                                                #
# --------------------------------------------------------------------------- #

Pathish = Union[str, PathLike[str], Path]
Command = Union[str, Sequence[str]]

# --------------------------------------------------------------------------- #
# endregion Types                                                             #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class ClassLoader(IWattleflow):
    def __init__(
        self,
        class_path: str,
        *args,
        **kwargs,
    ):

        level: Union[int, str] = kwargs.pop("level", NOTSET)
        handler: Optional[Handler] = kwargs.pop("handler", None)

        super().__init__()

        # Stdlib logger (no concrete.AuditLogger — keeps helpers below domains).
        # Stdlib accepts only exc_info/extra/stack_info/stacklevel as kwargs, so
        # context goes into the message via lazy %-formatting.
        self.log = getLogger(self.__class__.__name__)
        if level:
            self.log.setLevel(level)
        if handler is not None and handler not in self.log.handlers:
            self.log.addHandler(handler)

        self.log.debug("%s: class_path=%s", Event.Constructor.value, class_path)

        try:
            module_path, class_name = class_path.rsplit(".", 1)
        except ValueError as e:
            self.log.error("%s: invalid class path %r: %s", Event.Constructor.value, class_path, e)
            raise ValueError(f"Invalid class path: {class_path}") from e

        try:
            module = import_module(module_path)
        except ModuleNotFoundError as e:
            self.log.error("module not found %r: %s", module_path, e)
            raise

        # FIX: previously warning fired unconditionally *before* the hasattr
        # check, so every successful load wrongly reported the class as
        # unverified. Validate first, then debug-log the resolution.
        if not hasattr(module, class_name):
            error = f"Class '{class_name}' not found in module '{module_path}'"
            self.log.error("%s: %s", Event.Constructor.value, error)
            raise AttributeError(error)

        cls = getattr(module, class_name)
        self.cls = cls

        self.log.debug("%s: class resolved %s.%s", Event.Constructor.value, module_path, class_name)

        try:
            self.instance = cls(*args, **kwargs)
        except Exception as e:
            self.log.error("class instantiation failed for %s: %s", cls, e)
            raise

        self.log.debug("%s: class loaded %s", Event.Constructor.value, cls.__name__)


@final
class FileStorage:
    def __init__(self, repository_path: str, filename: str, create: bool, normalised=False):
        self.origin = Path(filename)
        self.path = Path(repository_path)

        # FIX: original used `and` for all three conditions, meaning the guard was only
        # triggered when the path was simultaneously not a directory AND not readable AND
        # create was False — a path that exists as a directory but is unreadable would
        # silently pass.  The correct intent is: raise if create is False AND the path
        # is either not a directory OR not readable.
        if (
            not create  # noqa: W503
            and (not os.path.isdir(self.path) or not os.access(self.path, os.R_OK))  # noqa: W503
        ):
            raise FileNotFoundError(f"Path doesn't exist or not accessible: {str(self.path)}")

        if create and self.path.exists() is False:
            self.path.mkdir(parents=True, exist_ok=True)

        name = Normaliser(self.origin.name).date().name() if normalised else self.origin.name

        self.filename = self.path.joinpath(name).with_suffix(self.origin.suffix)

    @property
    def size(self) -> int:
        return os.stat(self.filename).st_size

    def with_suffix(self, suffix: str) -> Path:
        return self.filename.with_suffix(suffix)

    def with_dir(self, directory=None, mkdir=True) -> Path:
        target = directory if directory else self.filename.stem
        out_dir = self.path.joinpath(target)
        resolved_base = self.path.resolve()
        resolved_out = out_dir.resolve()
        try:
            resolved_out.relative_to(resolved_base)
        except ValueError as e:
            raise ValueError(
                f"Directory '{directory}' escapes the repository root: {resolved_out}"
            ) from e

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
                if tuple(parts[i : i + len(marker_parts)]) == marker_parts:  # noqa: E203
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
            # Swallow after-call failures so the target's result is preserved.
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
        # FIX: os.sep is '\\' on Windows, but the SHELL environment variable always
        # uses forward-slash separators (e.g. '/usr/bin/bash').  Using os.sep as the
        # split delimiter returns the full path unchanged on Windows.  Path.name is
        # platform-agnostic and correctly extracts just the executable name.
        shell_path = os.environ.get("SHELL", "bash")
        return Path(shell_path).name

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
        def to_s(x):
            return (x or "").strip()

        shell = shell or self.shell

        if isinstance(command, str) and not use_shell:
            cmd_list: Sequence[str] = shlex.split(command)
        elif isinstance(command, (list, tuple)):
            cmd_list = list(command)
        elif isinstance(command, str) and use_shell:
            # SECURITY: passing a raw string to a shell interpreter enables command
            # injection. Pass the full command as a list instead, e.g.:
            #   ["bash", "-c", "ls | grep foo"]
            raise TypeError(
                "use_shell=True with a string command is not permitted. "
                "Pass command as a list to retain shell features safely, e.g. "
                '["bash", "-c", "your | pipeline"].'
            )
        else:
            raise TypeError(f"Unsupported command type: {type(command).__name__}")

        try:
            result = subprocess.run(
                args=cmd_list,
                text=True,
                capture_output=True,
                check=True,
                timeout=timeout,
                cwd=str(cwd) if cwd else None,
                env=env,
                shell=False,
            )
            return {
                "stdout": to_s(result.stdout),
                "stderr": to_s(result.stderr),
                "returncode": result.returncode,
            }
        except subprocess.CalledProcessError as e:
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
    def __init__(self, file_path: os.PathLike, create_dir=True):

        path_like = str(file_path).strip()

        if (not file_path) or (path_like == ""):
            raise ValueError("TempPathHelper.file_path is empty!")

        if path_like.startswith("TEMP"):
            path_like = gettempdir() + path_like[len("TEMP") :]

        self.source_path: Path = Path(path_like)

        if not (self.source_path.exists()) and (create_dir is True):
            self.source_path.mkdir(parents=True)

    @property
    def full_path(self) -> Path:
        return self.source_path.absolute()

    # FIX: previously annotated as `-> Path` but returns a str — annotation
    # corrected to match the actual return type.
    @property
    def str_path(self) -> str:
        return str(self.source_path.absolute())


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Global methods                                                       #
# --------------------------------------------------------------------------- #


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
            return Proxy(fn, before_call=before_call, after_call=after_call)(*args, **kwargs)

        return wrapper

    return _outer


# --------------------------------------------------------------------------- #
# endregion Global methods                                                    #
# --------------------------------------------------------------------------- #
