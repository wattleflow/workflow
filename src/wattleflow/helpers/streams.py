# Module Name: name helpers/streams.py
# Description: This modul contains concrete name stream classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence


from typing import Any, List
from .macros import TextMacros


class TextStream:
    def __init__(self, text: str = "", list_of_macros: List = None):
        if list_of_macros is None:
            list_of_macros = []
        self._macros = TextMacros(list_of_macros)
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
    def __init__(self, file_path: str = "", list_of_macros: List = None):
        self.file_path = file_path

        from os import path

        if not path.exists(file_path):
            raise FileNotFoundError("{}:{}".format(self.__class__.__name__, file_path))

        with open(file_path, "r") as file:
            content = file.read()

        return super().__init__(content, list_of_macros)

    def __repr__(self) -> str:
        return f'TextFileStream(content:"{self._content}")'
