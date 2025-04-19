# Module Name: name pathadder.py
# Description: This modul contains pathadder methods.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

import os
import glob
import sys


"""
import os

# Set SOURCE_PATH to a specific path
os.environ['SOURCE_PATH'] = '/your/path/filename.py'

# After that, call the function
override_paths()
show_paths()

"""


def get_source_path(path: str):
    source_path = os.getenv("SOURCE_PATH", path)
    return source_path


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
