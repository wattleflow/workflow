# Module Name: concrete/wattletest.py
# Description: This module contains concrete unittest classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

import gc
import os
import re
import logging
import tempfile

from fnmatch import fnmatch
from os import path, makedirs, walk
from typing import Generator, Optional
from shutil import copy2, copytree, rmtree
from unittest import TestCase

from wattleflow.concrete.logger import AuditLogger


TEST_NAME = "test_dir"


class WattleflowTestClass(TestCase):
    _paths: dict = {}
    _config_path: str = ""
    cleanup: bool = True

    @property
    def local_temp(self) -> str:
        return self._temp_dir.name
        # return getattr(self, TEST_NAME, "")

    def setUp(self):
        self.log = AuditLogger(
            level=getattr(self, "level", logging.INFO),
            handler=getattr(self, "handler", None),
        )

        super().setUp()

        self._temp_dir = tempfile.TemporaryDirectory(
            prefix="wattleflow_"
        )  # pylint: disable=consider-using-with  # noqa: E501

        self.set_path(TEST_NAME, self._temp_dir.name)

        for name, folder in self._paths.items():
            if not path.exists(folder):
                self.set_path(name=name, folder=folder)

    def copy_file(self, src: str, dst: str, normalise: bool = False) -> None:
        from wattleflow.helpers.system import check_path

        check_path(src, True)

        if normalise:
            # ako je dst direktorij, osiguraj ga pa dodaj normalizirani naziv
            makedirs(dst, exist_ok=True)
            dst = path.join(dst, self.normalise_file_name(src))

        # kreiraj parent direktorij po potrebi
        parent = path.dirname(dst) or "."
        if parent and not path.exists(parent):
            makedirs(parent, exist_ok=True)

        if not path.exists(dst):
            copy2(src=src, dst=dst)

    def copy_files(self, src: str, dst: str, dirs_exist: bool = True) -> None:
        """
        - Py>=3.8: copytree(dirs_exist_ok=True/False)
        - Py 3.7 fallback: if dst exists i dirs_exist=True, merge copy.
        """
        from wattleflow.helpers.system import check_path

        check_path(src, True)

        # osiguraj parent direktorij odredista
        parent = path.dirname(dst) or "."
        if parent and not path.exists(parent):
            makedirs(parent, exist_ok=True)

        # Pokušaj moderni API (Py>=3.8)
        try:
            copytree(src, dst, dirs_exist_ok=dirs_exist)  # type: ignore[call-arg]
            return
        except TypeError:
            # Py 3.7 nema dirs_exist_ok -> nastavi niže fallback
            pass
        except FileExistsError:
            if not dirs_exist:
                raise
            # ako je dozvoljeno postojanje, nastavi s merge ispod

        # Py 3.7 fallback: ako dst ne postoji, standardni copytree
        if not path.exists(dst):
            copytree(src, dst)
            return

        # Merge copy: rekurzivno kopiraj sadržaj
        for root, dirs, files in walk(src):
            rel = os.path.relpath(root, src)
            dest_root = path.join(dst, rel) if rel != "." else dst
            if not path.exists(dest_root):
                makedirs(dest_root, exist_ok=True)
            for d in dirs:
                dpath = path.join(dest_root, d)
                if not path.exists(dpath):
                    makedirs(dpath, exist_ok=True)
            for f in files:
                copy2(path.join(root, f), path.join(dest_root, f))

    def copy_normalised_files(
        self,
        src: str,
        dst: str,
        pattern: str,
        max_len: int = 30,
    ) -> None:
        from wattleflow.helpers.system import check_path

        check_path(src, True)
        makedirs(dst, exist_ok=True)

        for src_path in self.find_by_pattern(src, pattern):
            normalised_name = self.normalise_file_name(filename=src_path)
            self.copy_file(src_path, path.join(dst, normalised_name))

    def execute(self, cmd: str, shell: Optional[str] = None):
        from wattleflow.helpers.system import ShellExecutor

        command = ShellExecutor()
        return command.execute(cmd, shell)

    def find_by_pattern(
        self, directory: str, pattern: str
    ) -> Generator[str, None, None]:
        """
        Case-insensitive fnmatch pretraga datoteka po uzorku.
        """
        p = pattern.casefold()
        for root, _, files in walk(directory):
            for file in files:
                if fnmatch(file.casefold(), p):
                    yield path.join(root, file)

    def make_dir(self, dst: str, mode: int = 0o755) -> None:
        makedirs(dst, mode=mode, exist_ok=True)

    def normalise_file_name2(
        self,
        filename: str,
        max_len: int = 20,
        pattern: str = r"[\s_,\-]+",
        replacement: str = "-",
    ) -> str:
        basename = path.basename(filename).strip().lower()
        stem, ext = path.splitext(basename)

        stem = re.sub(pattern, replacement, stem)
        stem = re.sub(r"-{2,}", "-", stem).strip("-")

        if len(stem) > max_len:
            stem = stem[:max_len]

        return f"{stem}{ext}"

    def normalise_file_name(
        self,
        filename: str,
        replacement: str = "-",
    ) -> str:

        from pathlib import Path

        p = Path(filename)
        basename = p.name.strip().lower()
        stem, ext = Path(basename).stem, Path(basename).suffix.lower()

        import unicodedata

        norm = unicodedata.normalize("NFKD", stem)
        norm = norm.encode("ascii", "ignore").decode("ascii")

        norm = re.sub(r"[^a-z0-9]+", replacement, norm)

        if replacement:
            rep_esc = re.escape(replacement)
            norm = re.sub(rf"{rep_esc}{{2,}}", replacement, norm).strip(replacement)

        if not norm:
            norm = "file"

        raise FileExistsError(f"{norm}{ext}")
        return f"{norm}{ext}"

    def set_path(self, name: str, folder: str, exist_ok: bool = True) -> str:
        if name not in self._paths:
            if not path.exists(folder):
                makedirs(folder, exist_ok=exist_ok)
            self._paths[name] = folder
            setattr(self, name, folder)
        return self._paths[name]

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def tearDown(self) -> None:
        cleanup = getattr(self, "cleanup", None)
        if cleanup:
            for folder in self._paths.values():
                if path.exists(folder):
                    rmtree(folder, ignore_errors=True)

            # TemporaryDirectory cleanup
            try:
                self._temp_dir.cleanup()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        gc.collect()
        return super().tearDown()
