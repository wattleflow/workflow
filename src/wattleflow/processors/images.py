# Module Name: processors/tesseract.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains tesseract processors for handling image text.

import os
import pytesseract
from PIL import Image
from glob import glob
from typing import Generator
from wattleflow.concrete import DocumentFacade, GenericProcessor
from wattleflow.concrete.processor import T
from wattleflow.helpers import TextStream

# --------------------------------------------------------------------------- #
# IMPORTANT:
# This test case requires the pytesseract library.
# Ensure you have it installed using: pip install pytesseract
# The library is used to extract text from image files.
# --------------------------------------------------------------------------- #


class ImageToTextProcessor(GenericProcessor[DocumentFacade]):
    _search_path:str = ""
    def __init__(self, strategy_audit, blackboard, pipelines, allowed, **kwargs):
        super().__init__(strategy_audit, blackboard, pipelines, allowed, **kwargs)
        mask = (
            "**{}{}".format(os.path.sep, self.pattern)
            if self.recursive
            else self.pattern
        )
        self._search_path = os.path.join(self.source_path, mask)
        self._iterator = self.create_iterator()

    def create_iterator(self) -> Generator[T, None, None]:
        for file_path in glob(self._search_path, recursive=self.recursive):
            if os.access(file_path, os.R_OK) and os.stat(file_path).st_size > 0:
                image = Image.open(file_path)
                content = TextStream(pytesseract.image_to_string(image), macros=self.macros)
                yield self.blackboard.create(
                    processor=self,
                    file_path=file_path,
                    content=content,
                )
