# Module Name: name helpers/streams.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete name stream classes.

from .macros import TextMacros

class TextStream(str):
    def __new__(cls, text="", macros=None):
        obj = super().__new__(cls, text)

        obj._macros = TextMacros()
        if macros is not None:
            if not isinstance(macros, list):
                raise TypeError(f"Wrong [list] type: {type(macros).__name__}.")
            obj._macros.add(macros)
        obj._content = ""
        obj << text
        return obj

    @property
    def size(self):
        if not self._content:
            return 0
        return len(self._content.strip())

    def __add__(self, text):
        if not text:
            return self

        if isinstance(text, (list, tuple)):
            new_content = "\n".join(map(str, text)) + " "
        elif isinstance(text, dict):
            new_content = "\n".join(f"{k}: {v}" for k, v in text.items()) + " "
        else:
            new_content = f"{text} "

        self._content += self._macros.run(new_content)

        return self._content

    def __lshift__(self, item):
        return self + item

    def __repr__(self) -> str:
        return f'TextStream(content:"{self._content}")'
        # return f'TextStream(size:{self.size}, macros:{self._macros}, content:"{self._content}")'

    def __str__(self) -> str:
        return self._content.strip()

    def clear(self):
        self._content = ""


class TextListStream(str):
    def __new__(cls, text="", macros=None):
        obj = super().__new__(cls, text)
        obj._words = []
        obj._macros = TextMacros()
        if macros is not None:
            if not isinstance(macros, list):
                raise TypeError(f"Expected list, got {type(macros).__name__}")
            obj.add(macros)
        obj << text
        return obj

    def __add__(self, text):
        if not text:
            return self

        if isinstance(text, (list, tuple)):
            new_content = "\n".join(map(str, text)) + " "
        elif isinstance(text, dict):
            new_content = "\n".join(f"{k}: {v}" for k, v in text.items()) + " "
        else:
            new_content = f"{text} "

        content = self._macros.run(new_content)

        for word in content.split(" "):
            word = word.strip()
            if word not in self._words:
                if not word == "":
                    self._words.append(word)

        return self._words

    def __lshift__(self, text):
        return self + text

    def __str__(self) -> str:
        if not len(self._words) > 0:
            return ""
        return "\n".join(self._words)

    def __repr__(self) -> str:
        return f'TextDictionaryStream("size:{self.size}, {self._words}")'

    @property
    def size(self) -> int:
        return len(self._words)
