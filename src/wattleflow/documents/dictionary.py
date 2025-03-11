# Module Name: documents/dictionary.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains DictDocument class.

from wattleflow.concrete.document import Document


# Dict document (dict)
class DictDocument(Document[dict]):
    def __init__(self, **kwargs):
        super().__init__()
        # self._data = {}
        data = kwargs if kwargs else {}
        self.update_content(data)

    @property
    def size(self):
        return self._data
