# Module Name: core/helpers/item.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul has ItemDocument class.

from wattleflow.concrete import Document


# Document that works with item
class ItemDocument(Document[str]):
    def __init__(self, item: str):
        super().__init__()
        self._item = item
        self._data = ""

    @property
    def item(self) -> str:
        return self._item
