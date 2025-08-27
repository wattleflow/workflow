# Module Name: strategies/write/text_document.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains text strategy write classes.

import os
from wattleflow.core import IRepository, ITarget, IWattleflow
from wattleflow.concrete import Document
from wattleflow.concrete.strategy import StrategyWrite
from wattleflow.constants import Event
from wattleflow.helpers import Attribute, TextStream


class WriteTextDocumentToFile(StrategyWrite):
    def execute(self, caller: IWattleflow, document: ITarget, *args, **kwargs) -> bool:
        self.debug(
            msg=Event.Executing.value,
            caller=caller.name,
            document=document.identifier,
            *args,
            **kwargs,
        )

        Attribute.mandatory(caller=self, name="repository", cls=IRepository, **kwargs)

        storage_path = Attribute.getattr(self.repository, "storage_path")
        storage_name = "{}.txt".format(os.path.join(storage_path, document.identifier))

        content: Document = document.specific_request()
        content = TextStream(document.specific_request())

        if not content.size > 0:
            self.warning(
                msg=Event.Executing.value,
                id=document.identifier,
                size=content.size,
            )
            return False

        if not os.path.exists(storage_path):
            os.makedirs(storage_path, exist_ok=True)

        with open(storage_name, "w") as file:
            file.write(str(content))

        self.info(
            msg=Event.Written.value,
            id=document.identifier,
            storage_name=storage_name,
            size=content.size,
        )

        return True
