# Module Name: core/processors/excel.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains excel handling processor class.

import os
import pandas as pd
from glob import glob
from typing import Generator
from wattleflow.concrete import DocumentFacade, GenericProcessor
from wattleflow.concrete.processor import T

# --------------------------------------------------------------------------- #
# IMPORTANT:
# This test case requires the openpyxl library.
# Ensure you have it installed using: pip install openpyxl
# The library is used to extract dataframes from excel worksheets.
# --------------------------------------------------------------------------- #


class ExcelWorkbookProcessor(GenericProcessor[DocumentFacade]):
    def __init__(
        self,
        strategy_audit,
        blackboard,
        pipelines,
        source_path,
        pattern,
        recursive,
        repository_path,
        workbooks,
    ):
        super().__init__(
            strategy_audit, blackboard, pipelines, repository_path=repository_path
        )
        pattern = "**/{}".format(pattern) if recursive else pattern
        self._workbooks = workbooks
        self._recursive = recursive
        self._search_path = os.path.join(source_path, pattern)
        self._iterator = self.create_iterator()

    @property
    def workbooks(self) -> dict:
        return self._workbooks

    def create_iterator(self) -> Generator[T, None, None]:
        for file_path in glob(self._search_path, recursive=self._recursive):
            with pd.ExcelFile(file_path) as excel_data:
                for sheet_name in excel_data.sheet_names:
                    yield self.blackboard.create(
                        processor=self,
                        file_path=file_path,
                        sheet_name=sheet_name,
                        workbooks=self._workbooks,
                    )
