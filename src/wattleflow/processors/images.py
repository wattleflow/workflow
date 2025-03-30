# Module Name: processors/tesseract.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains tesseract processors for handling image text.

import os
import pytesseract
from PIL import Image
from glob import glob
from logging import Handler, INFO
from typing import Generator, Optional
from wattleflow.core import IBlackboard, IPipeline, T
from wattleflow.concrete import DocumentFacade, GenericProcessor
from wattleflow.constants import Event
from wattleflow.helpers import TextStream

# --------------------------------------------------------------------------- #
# IMPORTANT:
# This test case requires the pytesseract library.
# Ensure you have it installed using: pip install pytesseract
# The library is used to extract text from image files.
# --------------------------------------------------------------------------- #


class ImageToTextProcessor(GenericProcessor[DocumentFacade]):
    _search_path: str = ""

    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: IPipeline,
        level: int = INFO,
        handler: Optional[Handler] = None,
        **kwargs,
    ):
        GenericProcessor.__init__(
            self, blackboard, pipelines, level=level, handler=handler, **kwargs
        )

        mask = (
            "**{}{}".format(os.path.sep, self.pattern)
            if self.recursive
            else self.pattern
        )
        self._search_path = os.path.join(self.source_path, mask)

    def create_iterator(self) -> Generator[T, None, None]:
        for file_path in glob(self._search_path, recursive=self.recursive):
            self.debug(msg=Event.Iterating.value, path=file_path)
            try:
                if os.access(file_path, os.R_OK) and os.stat(file_path).st_size > 0:
                    image = Image.open(file_path)
                    content = TextStream(
                        pytesseract.image_to_string(image),
                        macros=self.macros,
                    )

                    self.info(msg=Event.Iterating.value, file_path=file_path)

                    yield self.blackboard.create(
                        processor=self,
                        file_path=file_path,
                        content=content,
                    )

                else:
                    self.warning(msg="File not accessible", filename=file_path)
            except Exception as e:
                self.critical(msg=str(e))
                raise
