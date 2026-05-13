# Module name: pathadder.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module provides helper functions for managing and dynamically adjusting
Python import paths within the Wattleflow framework. It enables locating,
overriding, and displaying source paths to support flexible module resolution
during runtime.

import os

# Set SOURCE_PATH to a specific path
os.environ['SOURCE_PATH'] = '/your/path/filename.py'

# After that, call the function
override_paths()
show_paths()

"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import os
import glob
import sys

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Global methods                                                       #
# --------------------------------------------------------------------------- #


def get_source_path(path: str):
    source_path = os.getenv("SOURCE_PATH", path)
    return source_path


def _validate_source_path(path: str) -> str:
    """Validate path before inserting into sys.path.

    Rejects relative paths and paths containing traversal sequences to
    prevent environment-variable-based sys.path injection attacks.
    """
    resolved = os.path.realpath(path)
    if not os.path.isabs(resolved):
        raise ValueError(f"SOURCE_PATH must be absolute, got: {path!r}")
    if not os.path.isdir(resolved):
        raise ValueError(f"SOURCE_PATH does not exist or is not a directory: {path!r}")
    return resolved


def override_paths(show=False, path: str = "."):
    search_path = get_source_path(path)

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
                source_path = _validate_source_path(source_path)
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


def show_paths():
    for p in sys.path:
        print(p)


# --------------------------------------------------------------------------- #
# endregion Global methods                                                    #
# --------------------------------------------------------------------------- #
