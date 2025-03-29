# Module Name: core/processors/excel.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains excel handling processor class.

import os
import pandas as pd
from glob import glob
from logging import Handler, INFO
from typing import Generator, Optional
from wattleflow.core import IBlackboard, IPipeline
from wattleflow.concrete import DocumentFacade, GenericProcessor
from wattleflow.concrete.processor import T
from wattleflow.constants.enums import Event

# --------------------------------------------------------------------------- #
# IMPORTANT:
# This test case requires the openpyxl library.
# Ensure you have it installed using:
#   pip install openpyxl
# The library is used to extract dataframes from excel worksheets.
# --------------------------------------------------------------------------- #


class ExcelWorkbookProcessor(GenericProcessor[DocumentFacade]):
    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: list,
        source_path: str,
        pattern: str,
        recursive: bool,
        workbooks: list,
        level: int = INFO,
        handler: Optional[Handler] = None,
    ):
        pattern = "**/{}".format(pattern) if recursive else pattern
        self._workbooks = workbooks
        self._recursive = recursive
        self._search_path = os.path.join(source_path, pattern)

        GenericProcessor.__init__(
            self,
            blackboard=blackboard,
            pipelines=pipelines,
            allowed=[],
            level=level,
            handler=handler,
        )

        self.debug(
            msg=Event.Initialised.value,
            search_path=self._search_path,
            recursive=self._recursive,
            allowed=self._allowed,
            pipelines=[p.name for p in pipelines if isinstance(p, IPipeline)],
        )

    @property
    def workbooks(self) -> dict:
        return self._workbooks

    def create_iterator(self) -> Generator[T, None, None]:
        self.debug(msg="create_iterator", message="START")
        for file_path in glob(self._search_path, recursive=self._recursive):
            self.debug(msg=Event.Processing.value, file_path=file_path)
            with pd.ExcelFile(file_path) as excel_data:
                for sheet_name in excel_data.sheet_names:
                    self.info(
                        msg=Event.Processing.value,
                        file_path=file_path,
                        sheet_name=sheet_name,
                    )
                    yield self.blackboard.create(
                        processor=self,
                        file_path=file_path,
                        sheet_name=sheet_name,
                        workbooks=self._workbooks,
                    )
        self.debug(msg="create_iterator", message="END")
