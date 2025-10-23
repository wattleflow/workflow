# Module Name: text_document.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This module provides strategies for generating and storing TextDocuments
# within the Wattleflow Workflow framework. It includes utilities to create,
# manage, and maintain text-based document objects efficiently.

"""
This module defines utilities for creating and writing TextDocuments
within the Wattleflow Workflow framework. It provides strategies to
generate and manage text-based document objects efficiently.
"""

from datetime import datetime
from typing import Optional

from wattleflow.core import (
    IPipeline,
    IProcessor,
    IRepository,
    ITarget,
    IWattleflow,
)
from wattleflow.concrete import (
    DocumentFacade,
    StrategyCreate,
    StrategyWrite,
)
from wattleflow.constants import Event
from wattleflow.helpers import (
    Attribute,
)

from wattleflow.core import IProcessor, ITarget, IWattleflow
from wattleflow.concrete.document import DocumentFacade
from wattleflow.concrete.strategy import StrategyCreate
from wattleflow.constants import Event
from wattleflow.documents import FileDocument
from wattleflow.drivers import FileTypes
from wattleflow.helpers import TextStream


class CreateTextDocument(StrategyCreate):
    def execute(self, caller: IWattleflow, *args, **kwargs) -> Optional[ITarget]:
        self.debug(
            msg=Event.Execute.value,
            step=Event.Started.value,
            caller=caller,
            kwargs=len(kwargs),
        )
        Attribute.evaluate(caller=self, target=caller, expected_type=IProcessor)
        Attribute.mandatory(self, "filename", str, **kwargs)
        Attribute.mandatory(self, "content", str, **kwargs)

        document = FileDocument(filename=self.filename, **kwargs)  # type: ignore
        facade = DocumentFacade(document)

        content = TextStream(self.content)  # type: ignore
        self.debug(
            msg=Event.ProcessingTask.value,
            file_path=self.filename,  # type: ignore
            size=document.size,
        )

        document.update_metadata("created_by", caller.name)
        document.update_metadata("created_at", datetime.now())
        document.update_content(str(content))

        self.debug(
            msg=Event.Created.value,
            step=Event.Completed.value,
            document=document,
            size=document.size,
        )

        return facade


class WriteTextDocument(StrategyWrite):
    def execute(self, caller: IWattleflow, facade: ITarget, *args, **kwargs) -> bool:
        self.debug(
            msg=Event.Execute.value,
            caller=caller,
            document=facade,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=caller, expected_type=IPipeline)
        Attribute.mandatory(caller=self, name="repository", cls=IRepository, **kwargs)
        Attribute.mandatory(caller=self, name="processor", cls=IProcessor, **kwargs)

        # Using a driver for data persistence.
        document: YoutubeGraph = document.request()  # type: ignore
        filename: str = doc.metadata.get("id", str(doc.identifier))  # type: ignore
        filename = Path(filename).with_suffix(".json")  # type: ignore

        if not doc.size > 0:  # type: ignore
            self.warning(
                msg=Event.Execute.value,
                step=Event.Check.value,
                error="Text content is feeling a bit empty today!",
                size=document.size,
                filename=filename,
            )
            return False

        # Update the document metadata.
        document.update_metadata("stored_by", caller.name)
        document.update_metadata("stored_at", datetime.now())

        output = self.repository.driver.write(  # type: ignore
            filename=filename,
            ftype=FileTypes.text,
            document=document,
        )  # type: ignore

        self.debug(
            msg=Event.Created.value,
            step=Event.Completed.value,
            document=document,
            output=output,
            size=document.size,
        )

        return True
