# Module Name: helpers/localmodels.py
# Description: This modul contains classes for retrieving and copying
#              localy downloaded models.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

import os
import glob


class StoredModels:
    def __init__(self, name: str, path: str):
        self.name = name
        self.base_path = os.path.abspath(path)

    @property
    def model(self) -> str:
        safe_name = self.name.replace("/", "--")
        search_pattern = os.path.join(
            self.base_path, f"models--{safe_name}", "snapshots", "*"
        )
        matches = glob.glob(search_pattern)

        for match in matches:
            if self._is_valid_model_dir(match):
                return match

        raise FileNotFoundError(
            f"Model '{self.name}' nije pronađen u '{self.base_path}'."
        )

    def _is_valid_model_dir(self, directory: str) -> bool:
        valid_files = ["pytorch_model.bin", "model.safetensors", "config.json"]
        files = os.listdir(directory)
        return any(file in files for file in valid_files)


class DownloadedModels:
    def __init__(self, base_path: str = None):
        self.base_path = os.path.abspath(
            base_path or os.path.expanduser("~/.cache/huggingface")
        )

    def copy_models(self, destination: str):
        destination = os.path.abspath(destination)
        os.makedirs(destination, exist_ok=True)

        import shutil

        for model_name, model_path in self.list_models():
            dest_path = os.path.join(destination, model_name)
            if not os.path.exists(dest_path):
                shutil.copytree(model_path, dest_path)
                print(f"✔ Kopirano: {model_name} → {dest_path}")
            else:
                print(f"ℹ Preskočeno (već postoji): {model_name}")

    def list_models(self) -> list:
        models_dir = os.path.join(self.base_path, "hub")
        search_pattern = os.path.join(models_dir, "models--*", "snapshots", "*")

        model_paths = []
        for path in glob.glob(search_pattern):
            if self._is_valid_model_dir(path):
                model_name = self._extract_model_name(path)
                model_paths.append((model_name, path))

        return model_paths

    def _is_valid_model_dir(self, directory: str) -> bool:
        required_files = ["pytorch_model.bin", "model.safetensors", "config.json"]
        try:
            files = os.listdir(directory)
            return any(f in files for f in required_files)
        except FileNotFoundError:
            return False

    def _extract_model_name(self, path: str) -> str:
        # Izvlači ime modela iz staze npr. .../models--facebook--bart-base/...
        parts = path.split(os.sep)
        for part in parts:
            if part.startswith("models--"):
                return part.replace("models--", "").replace("--", "/")
        return "unknown"
