# Module name: streams.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence
#
# History:
#   2024-06-01: Initial creation of the TextStream and TextFile. Stream classes for handling text-based streams with macro processing capabilities.
#   2026-03-16: Added file size limit check to TextFileStream to prevent OOM issues with large files.


"""
Description: This module defines concrete classes for handling name streams within the
Wattleflow framework. It provides structured tools for managing and
processing stream-based naming operations.
"""

__FILE_SIZE_LIMIT__ = 50 * 1024 * 1024  # 50 MB

from typing import Any, List, Optional
from .macros import TextMacros


class TextStream:

    def __init__(self, text: str = "", macros: Optional[List] = None):
        if macros is None:
            macros = []
        self._macros = TextMacros(macros)
        self._segments: List[str] = []
        if text:
            self.__append__(text)

    def __add__(self, value: Any) -> "TextStream":
        return self.__append__(value)

    def __append__(self, value: Any) -> "TextStream":
        if value is None:
            return self
        if isinstance(value, (str, bytes)) and not value:
            return self
        if isinstance(value, (list, tuple, dict)) and not value:
            return self

        if isinstance(value, (list, tuple)):
            new_content = "\n".join(map(str, value)) + " "
        elif isinstance(value, dict):
            new_content = "\n".join(f"{k}: {v}" for k, v in value.items()) + " "
        else:
            new_content = f"{value} "

        processed = self._macros.run(new_content)
        self._segments.append(processed)

        return self

    def __lshift__(self, item: Any) -> "TextStream":
        return self.__append__(item)

    @property
    def content(self) -> str:
        return "".join(self._segments)

    @property
    def size(self) -> int:
        return len(self.content.strip())

    def __str__(self) -> str:
        return self.content.strip()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.content!r})"

    def clear(self) -> None:
        self._segments.clear()


class TextFileStream(TextStream):
    def __init__(
        self,
        file_path: str = "",
        encoding: str = "utf-8",
        macros: Optional[List] = None,
    ):

        from pathlib import Path

        self.filename: Path = Path(file_path)

        if not self.filename.exists():
            from wattleflow.concrete.exception import AuditException

            raise AuditException(
                caller=self,
                error=f"File not found {self.filename.name}",
                file_path=file_path,
            )

        # Security check: limit file size to prevent memory issues - OOM
        file_size = self.filename.stat().st_size
        if file_size > __FILE_SIZE_LIMIT__:
            from wattleflow.concrete.exception import AuditException

            raise AuditException(
                caller=self,
                error=f"File too large: {file_size} bytes (max {__FILE_SIZE_LIMIT__})",
                file_path=file_path,
            )

        content = self.filename.read_text(encoding=encoding)

        super().__init__(content, macros)

    def __repr__(self) -> str:
        return f'TextFileStream(content:"{self.content[:10]}", size: "{self.size}")'
