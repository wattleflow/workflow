# Module Name: strategies/create/text_document.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains create text strategy classes.

from wattleflow.core import IProcessor, T
from wattleflow.concrete.document import DocumentFacade
from wattleflow.concrete.strategy import StrategyCreate
from wattleflow.constants import Event
from wattleflow.helpers import TextStream


class CreateTextDocument(StrategyCreate):
    def execute(self, processor, *args, **kwargs) -> T:
        self.evaluate(processor, IProcessor)
        self.mandatory(name="file_path", cls=str, **kwargs)
        self.mandatory(name="content", cls=str, **kwargs)

        content = TextStream(self.content)
        self.debug(
            msg=Event.ProcessingTask.value,
            file_path=self.file_path,
        )

        from wattleflow.documents.file import FileDocument

        document = DocumentFacade(FileDocument(self.file_path))
        document.update_content(str(content))
        self.info(
            msg=Event.TaskCompleted.value,
            id=document.identifier,
            size=content.size,
        )

        return document
