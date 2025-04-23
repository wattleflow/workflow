# Module Name: helpers/system.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains path handling system classes and methods.


import os
import platform
import subprocess
import functools
from typing import final
from wattleflow.constants.keys import KEY_CONFIG_FILE_NAME


class Proxy:
    def __init__(self, target_method, before_call=None, after_call=None):
        """
        Proxy for dependency method call dependency injection.

        :param target_method: Original interecepted method name
        :param before_call: Method to be called before the method
        :param after_call: Function to be called after the method
        """
        self.target_method = target_method
        self.before_call = before_call
        self.after_call = after_call

    def __call__(self, *args, **kwargs):
        if self.before_call:
            self.before_call(*args, **kwargs)

        result = self.target_method(*args, **kwargs)

        if self.after_call:
            self.after_call(result)

        return result


def decorator(target_method):
    """
    Decorator for replacing the method with object.
    """

    @functools.wraps(target_method)
    def wrapper(*args, **kwargs):
        return Proxy(target_method)(*args, **kwargs)

    return wrapper


@final
class Project:
    root: str = ""
    config: str = ""

    def __init__(
        self, file_path: str, root_marker: str, config_name: str = KEY_CONFIG_FILE_NAME
    ):
        path = os.path.abspath(file_path)
        parts = path.split(os.sep)
        marker_parts = root_marker.split(os.path.sep)

        try:
            index = parts.index(marker_parts[0])
            for i, part in enumerate(marker_parts[1:], start=1):
                if parts[index + i] != part:
                    raise ValueError("Root marker not found in a given path.")
            self.root = os.sep.join(parts[: index + len(marker_parts)])
        except (ValueError, IndexError):
            self.root = os.path.dirname(path)

        if not os.path.exists(self.root):
            raise FileNotFoundError(f"Project [{self.root}] path is not found.")

        self.config = "{}{}{}".format(self.root, os.path.sep, config_name)


@final
class CheckPath:
    def __init__(self, file_path, owner=None):
        self.path = str(file_path) if isinstance(file_path, list) else file_path

        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Path not found: {self.path}.")

    def __str__(self):
        return self.path


@final
class LocalPath:
    def __init__(self, file_path, owner=None):
        self.owner = owner
        self.path = str(file_path) if isinstance(file_path, list) else file_path

    def exists(self) -> bool:
        return not os.path.exists(self.path)

    def create(self, existok=True, mode=None):
        if not os.path.exists(self.path):
            if mode:
                os.makedirs(self.path, exist_ok=existok, mode=mode)
            else:
                os.makedirs(self.path, exist_ok=existok)


class ShellExecutor:
    def __init__(self):
        self.os_name = platform.system().lower()
        self.shell = self.detect_shell()

    def detect_shell(self):
        if self.os_name == "windows":
            return "powershell" if self.is_powershell_available() else "cmd"
        return "bash"

    def is_powershell_available(self):
        try:
            subprocess.run(
                ["powershell", "-Command", "Get-Host"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def execute(self, command, shell=None):
        shell = shell or self.shell
        if shell == "cmd":
            cmd = ["cmd", "/c", command]
        elif shell == "powershell":
            cmd = ["powershell", "-Command", command]
        else:
            cmd = ["bash", "-c", command]

        try:
            result = subprocess.run(cmd, text=True, capture_output=True, check=True)
            return {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            }
        except subprocess.CalledProcessError as e:
            return {
                "stdout": e.stdout.strip(),
                "stderr": e.stderr.strip(),
                "returncode": e.returncode,
            }
        except FileNotFoundError:
            return {"error": f"Shell '{shell}' not found on the os."}
