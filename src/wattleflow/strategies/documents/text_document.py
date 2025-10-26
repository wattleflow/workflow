# Module name: text_document.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
from datetime import datetime
from pathlib import Path
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
from wattleflow.documents.file import FileDocument
from wattleflow.drivers import FileTypes
from wattleflow.helpers import Attribute, TextStream


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
        document: FileDocument = facade.request()  # type: ignore
        suffix = kwargs.get("suffix", ".txt")
        name = document.metadata.get("filename", document.identifier)
        filename = Path(str(name)).with_suffix(suffix)

        if not document.size > 0:  # type: ignore
            self.warning(
                msg=Event.Execute.value,
                step=Event.Check.value,
                error="Text content is feeling a bit empty today!",
                document=document,
                size=document.size,
                filename=filename,
            )
            return False

        # Update the document metadata.
        document.update_metadata("stored_by", caller.name)
        document.update_metadata("stored_at", document.utc_time_stamp())

        output = self.repository.driver.write(  # type: ignore
            filename=filename,
            ftype=FileTypes.TEXT,
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
