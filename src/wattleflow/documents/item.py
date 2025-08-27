# Module Name: documents/item.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence
# Description: This modul has string ItemDocument class.

from logging import NOTSET, Handler
from typing import Optional
from wattleflow.concrete import Document


class ItemDocument(Document[str]):
    def __init__(
        self, filename: str, level: int = NOTSET, handler: Optional[Handler] = None
    ):
        Document.__init__(self, content="", level=level, handler=handler)
        self.update_metadata(key="filename", value=filename)

    @property
    def size(self) -> int:
        return len(getattr(self, "content", ""))
