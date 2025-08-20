# Module Name: documents/dictionary.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains DictDocument class.

from abc import ABC
from logging import NOTSET, Handler
from typing import Optional
from wattleflow.concrete.document import Document


class DictDocument(Document[dict], ABC):
    def __init__(
        self,
        content: dict,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        Document.__init__(self, content=content, level=level, handler=handler)

    @property
    def size(self) -> int:
        if not self.content:
            return 0
        return len(self.content)
