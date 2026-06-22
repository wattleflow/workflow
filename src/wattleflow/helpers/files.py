# Module name: helpers/files.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Shared, case-insensitive filesystem scanning for processors.

pathlib globbing is case-sensitive on case-sensitive filesystems (Linux) and
the ``case_sensitive`` kwarg only arrives in Python 3.12, while the framework
targets 3.11+. FileScanner rewrites each glob into case-insensitive character
classes so a single config entry (e.g. ``*.txt``) behaves identically on Linux,
Windows and macOS, and validates the ``pattern`` value so every YAML config
that uses it is held to the same format.

Example:
    from wattleflow.helpers import FileScanner

    for path in FileScanner.scan("/data", "*.txt", recursive=True):
        print(path)
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from collections.abc import Iterable, Iterator
from pathlib import Path
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["FileScanner"]

# --------------------------------------------------------------------------- #
# region FileScanner                                                          #
# --------------------------------------------------------------------------- #


class FileScanner:
    """Case-insensitive, multi-pattern filesystem scanning shared by processors."""

    DEFAULT_PATTERN = "*"

    @staticmethod
    def normalise(pattern: str | Iterable[str] | None) -> list[str]:
        """Validate a ``pattern`` config value and return a list of glob strings.

        Accepts a single glob string or a list/tuple of glob strings; ``None``
        means "match everything". Raises ``ValueError`` on any other shape so
        every YAML config that uses ``pattern`` is held to the same format.
        """
        if pattern is None:
            return [FileScanner.DEFAULT_PATTERN]

        if isinstance(pattern, str):
            raw: list = [pattern]
        elif isinstance(pattern, (list, tuple)):
            if not pattern:
                raise ValueError("pattern list must not be empty")
            raw = list(pattern)
        else:
            raise ValueError(
                f"pattern must be a string or list of strings, got {type(pattern).__name__}"
            )

        cleaned: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                raise ValueError(f"pattern entries must be strings, got {type(item).__name__}")
            text = item.strip()
            if not text:
                raise ValueError("pattern entries must not be empty")
            cleaned.append(text)
        return cleaned

    @staticmethod
    def caseless(pattern: str) -> str:
        """Rewrite a glob so each cased letter matches either case (``[xX]``).

        Glob metacharacters and existing ``[...]`` classes are left untouched.
        """
        out: list[str] = []
        in_class = False
        for ch in pattern:
            if ch == "[":
                in_class = True
                out.append(ch)
            elif ch == "]":
                in_class = False
                out.append(ch)
            elif ch.isalpha() and not in_class and ch.lower() != ch.upper():
                out.append(f"[{ch.lower()}{ch.upper()}]")
            else:
                out.append(ch)
        return "".join(out)

    @staticmethod
    def scan(
        search_path: str | Path,
        pattern: str | Iterable[str] | None = None,
        recursive: bool = False,
    ) -> Iterator[Path]:
        """Yield each file under ``search_path`` matching any pattern.

        Matching is case-insensitive; only files are yielded (directories are
        skipped). Results are de-duplicated by resolved path so overlapping
        patterns — or a case-insensitive filesystem — never yield a file twice.
        """
        base = Path(search_path)
        seen: set[Path] = set()
        for glob_pattern in FileScanner.normalise(pattern):
            caseless = FileScanner.caseless(glob_pattern)
            matches = base.rglob(caseless) if recursive else base.glob(caseless)
            for path in matches:
                if not path.is_file():
                    continue
                try:
                    resolved = path.resolve()
                except OSError:
                    resolved = path
                if resolved in seen:
                    continue
                seen.add(resolved)
                yield path


# --------------------------------------------------------------------------- #
# endregion FileScanner                                                       #
# --------------------------------------------------------------------------- #
