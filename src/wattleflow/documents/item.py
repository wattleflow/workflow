# Module name: item.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
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
