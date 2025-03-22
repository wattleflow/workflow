# Module Name: strategies/write/text_document.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains text strategy write classes.

import os
from wattleflow.core import IProcessor
from wattleflow.concrete.attribute import _NC
from wattleflow.concrete.strategy import StrategyWrite
from wattleflow.helpers import TextStream
from wattleflow.constants import Event


class WriteTextDocumentToFile(StrategyWrite):
    def execute(self, pipeline, repository, item, *args, **kwargs) -> bool:
        self.mandatory(name="processor", cls=IProcessor, **kwargs)

        pipe_name = _NC(pipeline).lower()
        storage_path = os.path.join(repository.storage_path, pipe_name)
        storage_name = "{}.txt".format(os.path.join(storage_path, item.identifier))
        content = TextStream(item.request())

        if not content.size >= 1:
            self.processor.audit(
                caller=pipeline,
                event=Event.Stopped,
                id=item.identifier,
                storage_path=storage_path,
                size=content.size,
                level=4,
            )
            return False

        if not os.path.exists(storage_path):
            os.makedirs(storage_path, exist_ok=True)

        with open(storage_name, "w") as file:
            file.write(str(content))

        self.processor.audit(
            caller=pipeline,
            event=Event.Stored,
            id=item.identifier,
            storage_name=storage_name,
            size=content.size,
            level=3,
        )

        return True
