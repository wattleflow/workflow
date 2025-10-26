# Module name: dataframe.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
from pandas import DataFrame
from logging import NOTSET, Handler
from typing import Optional
from wattleflow.concrete import Document


class DataFrameDocument(Document[DataFrame]):
    def __init__(
        self, content: DataFrame, level: int = NOTSET, handler: Optional[Handler] = None
    ):
        Document.__init__(self, content=content, level=level, handler=handler)

    @property
    def filename(self) -> str:
        return str(self.metadata.get("filename", ""))

    @filename.setter
    def filename(self, value: str) -> None:
        filename = value.strip()
        if not filename:
            raise ValueError("filename must be a non-empty string")
        self.update_metadata("filename", filename)

    @property
    def size(self) -> int:
        if isinstance(self.content, DataFrame):
            return len(self.content)
        return 0
