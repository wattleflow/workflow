# Module name: streams.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module defines concrete classes for handling name streams within the
Wattleflow framework. It provides structured tools for managing and
processing stream-based naming operations.
"""


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
        if not value:
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
            raise FileNotFoundError(
                "{}:{}".format(
                    self.__class__.__name__,
                    self.filename.name,
                )
            )

        content = self.filename.read_text(encoding=encoding)

        return super().__init__(content, macros)

    def __repr__(self) -> str:
        return f'TextFileStream(content:"{self.content[:10]}", size: "{self.size}")'
