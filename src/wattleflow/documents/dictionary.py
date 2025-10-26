# Module name: dictionary.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
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
