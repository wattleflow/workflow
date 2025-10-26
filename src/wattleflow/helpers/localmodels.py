# Module name: localmodels.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
import os
import glob
from typing import Optional


class StoredModels:

    def __init__(self, name: str, path: str):
        self.name = name
        self.base_path = os.path.abspath(path)

    @property
    def model_name(self) -> str:
        safe_name = self.name.replace("/", "--")
        search_pattern = os.path.join(
            self.base_path, f"models--{safe_name}", "snapshots", "*"
        )
        matches = glob.glob(search_pattern)

        for match in matches:
            if self._is_valid_model_dir(match):
                return match

        raise FileNotFoundError(f"Model '{self.name}' not found in '{self.base_path}'.")

    def _is_valid_model_dir(self, directory: str) -> bool:
        valid_files = ["pytorch_model.bin", "model.safetensors", "config.json"]
        files = os.listdir(directory)
        return any(file in files for file in valid_files)


class DownloadedModels:
    def __init__(self, base_path: Optional[str] = None):

        import importlib.util

        transformers_spec = importlib.util.find_spec("transformers")

        if base_path is None and transformers_spec:
            from transformers.utils.hub import TRANSFORMERS_CACHE

            self.base_path = TRANSFORMERS_CACHE
            # self.base_path = transformers_spec.utils.hub.TRANSFORMERS_CACHE
        elif base_path is not None:
            self.base_path = base_path
        else:
            self.base_path = os.path.expanduser("~/.cache/huggingface")
        # self.base_path = os.path.abspath(base_path or TRANSFORMERS_CACHE)

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
        # Provjera da li već sadrži 'hub'
        if "hub" not in self.base_path:
            models_dir = os.path.join(self.base_path, "hub")
        else:
            models_dir = self.base_path

        print(f"INFO: {models_dir}")

        # Correct pattern za HuggingFace models
        search_pattern = os.path.join(models_dir, "models--*", "snapshots", "*")

        model_paths = []
        for path in glob.glob(search_pattern):
            if self._is_valid_model_dir(path):
                model_name = self._extract_model_name(path)
                model_paths.append((model_name, path))

        return model_paths

    def list_models_old(self) -> list:
        print(f"INFO: {self.base_path}")
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
        # Retrieve model from path .../models--facebook--bart-base/...
        parts = path.split(os.sep)
        for part in parts:
            if part.startswith("models--"):
                return part.replace("models--", "").replace("--", "/")
        return "unknown"
