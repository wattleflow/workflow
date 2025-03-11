# Module Name: documents/data_frame.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains DataFrameDocument class.

from pandas import DataFrame
from wattleflow.concrete.document import Document


class DataFrameDocument(Document[DataFrame]):
    def __init__(self, filename: str):
        super().__init__()
        self._filename = filename

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def size(self) -> int:
        if not self._content:
            return 0

        if self._content.empty:
            return 0

        return len(self._content)
