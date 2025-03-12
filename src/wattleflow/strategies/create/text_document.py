# Module Name: strategies/create/text_document.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains create text strategy classes.

from wattleflow.core import IProcessor, T
from wattleflow.concrete import DocumentFacade, FileDocument, TextStream
from wattleflow.concrete import StrategyCreate
from wattleflow.constants import Event


class CreateTextDocument(StrategyCreate):
    def execute(self, processor, *args, **kwargs) -> T:
        self.evaluate(processor, IProcessor)
        self.mandatory(name="file_path", cls=str, **kwargs)
        self.mandatory(name="content", cls=str, **kwargs)

        content = TextStream(self.content)
        processor.audit(
            caller=self,
            event=Event.Creating,
            filename=self.file_path,
            level=5,
        )

        document = DocumentFacade(FileDocument(self.file_path))
        document.update_content(content)

        processor.audit(
            caller=self,
            event=Event.Created,
            id=document.identifier,
            size=content.size,
            level=4,
        )

        return document
