# Module Name: core/processors/tika.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains tesseract processors for handling images.

import os
from glob import glob
from tika import parser
from typing import Generator
from wattleflow.concrete import DocumentFacade, GenericProcessor
from wattleflow.concrete.processor import T

# --------------------------------------------------------------------------- #
# IMPORTANT:
# This test case requires the pytesseract library.
# Ensure you have it installed using:
#   pip install tika
# The library is used to extract text from image files.
# --------------------------------------------------------------------------- #


class TikaTextProcessor(GenericProcessor[DocumentFacade]):
    def __init__(self, strategy_audit, blackboard, pipelines, **kwargs):
        super().__init__(strategy_audit, blackboard, pipelines, **kwargs)
        mask = (
            "**{}{}".format(os.path.sep, self.pattern)
            if self.recursive
            else self.pattern
        )
        self._search_path = os.path.join(self.source_path, mask)
        self._macros = []
        self._iterator = self.create_iterator()

    def create_iterator(self) -> Generator[T, None, None]:
        for file_path in glob(self._search_path, recursive=self.recursive):
            response = parser.from_file(file_path)
            content = response.get("content", "").strip()
            if len(content.strip()) > 0:
                yield self.blackboard.create(
                    processor=self,
                    file_path=file_path,
                    content=content,
                )
            else:
                print(f"[WARNING] Empty file: {file_path}")
