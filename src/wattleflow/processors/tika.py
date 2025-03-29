# Module Name: core/processors/tika.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains tesseract processors for handling images.

import os
from glob import glob
from tika import parser
from logging import Handler, INFO
from typing import Generator, Optional
from wattleflow.core import IBlackboard, T
from wattleflow.concrete import DocumentFacade, GenericProcessor
from wattleflow.constants import Event

# --------------------------------------------------------------------------- #
# IMPORTANT:
# This test case requires the pytesseract library.
# Ensure you have it installed using:
#   pip install tika
# The library is used to extract text from image files.
# --------------------------------------------------------------------------- #


class TikaTextProcessor(GenericProcessor[DocumentFacade]):
    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: list,
        level: int = INFO,
        handler: Optional[Handler] = None,
        **kwargs,
    ):
        GenericProcessor.__init__(
            self,
            blackboard=blackboard,
            pipelines=pipelines,
            level=level,
            handler=handler,
            **kwargs,
        )

        mask = (
            "**{}{}".format(os.path.sep, self.pattern)
            if self.recursive
            else self.pattern
        )

        self._search_path = os.path.join(self.source_path, mask)
        self._macros = []

        self.debug(
            msg=Event.Constructor.value,
            source_path=self.source_path,
            search_path=self._search_path,
            recursive=self.recursive,
            mask=mask,
        )

    def create_iterator(self) -> Generator[T, None, None]:
        for file_path in glob(self._search_path, recursive=self.recursive):
            self.info(msg=Event.Iterating.value, file_path=file_path)
            response = parser.from_file(file_path)
            yield self.blackboard.create(
                processor=self,
                file_path=file_path,
                content=response.get("content", "").strip(),
            )
