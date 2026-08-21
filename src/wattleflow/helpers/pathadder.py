# Module name: pathadder.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""Runtime sys.path adjustment driven by the SOURCE_PATH environment variable."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import os
import glob
import sys
from typing import ClassVar

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["SourcePath"]


# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


# v0.0.0.97 (NFR-ORG-05): the environment key, the injection guard and the
# search live in one class — the guard is not a module-level function.
class SourcePath:
    """Locates a source tree and prepends it to `sys.path`."""

    ENV: ClassVar[str] = "SOURCE_PATH"

    @classmethod
    def configured(cls, path: str) -> str:
        return os.getenv(cls.ENV, path)

    @classmethod
    def _validate(cls, path: str) -> str:
        """Validate path before inserting into sys.path.

        Rejects relative paths and paths containing traversal sequences to
        prevent environment-variable-based sys.path injection attacks.
        """
        resolved = os.path.realpath(path)
        if not os.path.isabs(resolved):
            raise ValueError(f"{cls.ENV} must be absolute, got: {path!r}")
        if not os.path.isdir(resolved):
            raise ValueError(f"{cls.ENV} does not exist or is not a directory: {path!r}")
        return resolved

    @classmethod
    def override(cls, show: bool = False, path: str = ".") -> None:
        search_path = cls.configured(path)

        to_search = sys.path[:]
        searched = set()

        while to_search:
            path = to_search.pop(0)

            if path in searched:
                continue

            searched.add(path)

            search_pattern = os.path.join(path, "**", search_path)
            found_files = glob.glob(search_pattern, recursive=True)

            if found_files:
                source_path = os.path.dirname(found_files[0])
                try:
                    source_path = cls._validate(source_path)
                except ValueError as e:
                    if show:
                        print(f"[WARN] : {e}")
                    break
                sys.path.insert(0, source_path)
                if show:
                    print(f"[INFO] : Searched path found: {source_path}")
                break

            parent_dir = os.path.dirname(path)
            while parent_dir and parent_dir != path:
                to_search.append(parent_dir)
                path = parent_dir
                parent_dir = os.path.dirname(path)

    @staticmethod
    def show() -> None:
        for p in sys.path:
            print(p)


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
