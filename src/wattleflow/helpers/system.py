# Module Name: core/helpers/system.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains path handling system classes and methods.


import subprocess
import platform
from os import path, makedirs


class Project:
    def __init__(self, dir: str, level_up: int = 3):
        start_path = path.dirname(path.abspath(dir))
        path_parts = start_path.split(path.sep)

        self.root_path = (
            str(path.sep).join(path_parts[:-level_up])
            if (len(path_parts) > level_up)
            else start_path
        )

        if not path.exists(self.root_path):
            raise FileNotFoundError(f"Project [{self.root_path}] path is not found.")


class CheckPath:
    def __init__(self, file_path, owner=None):
        self.file_path = str(file_path) if isinstance(file_path, list) else file_path

        if not path.exists(self.file_path):
            raise FileNotFoundError(f"Path [{self.file_path}] is not found.")

    def __str__(self):
        return self.file_path


class LocalPath:
    def __init__(self, file_path, owner=None):
        self.owner = owner
        self.file_path = str(file_path) if isinstance(file_path, list) else file_path

    def exists(self):
        if not path.exists(self.file_path):
            raise FileNotFoundError(self.file_path)

    def create(self, existok=True, mode=None):
        if not path.exists(self.file_path):
            if mode:
                makedirs(self.file_path, exist_ok=existok, mode=mode)
            else:
                makedirs(self.file_path, exist_ok=existok)


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
