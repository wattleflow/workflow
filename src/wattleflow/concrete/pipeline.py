# Module Name: concrete/pipeline.py
# Description: This modul contains pipeline classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence

from abc import ABC, abstractmethod
from logging import Handler, NOTSET
from typing import Optional
from wattleflow.core import IProcessor, IPipeline
from wattleflow.concrete import Attribute, AuditLogger, _NC


"""
1. Inheritance & Dependencies
    Inherits from:
        - IPipeline: Defines the pipeline interface.
        - Attribute: Provides evaluate(), allowed(), and other helper methods.
    Depends on:
        - IPipeline: Implements the IPipeline interface.
        - IProcessor: Used for validating processor in process().

2. Core Responsibilities
    Automatically assigns the pipeline’s class name as its identifier.
    Processing items (process)
        - Abstract method (@abstractmethod) ensures child classes must implement process().
        - Calls self.evaluate(processor, IIterator) to validate that processor is an IIterator.


Example:

class DataFrameCleanupPipeline(GenericPipeline):
    def process(self, processor, item) -> None:

        dataframe: pd.DataFrame = item.request()
        self.evaluate(dataframe, pd.DataFrame)

        if dataframe.empty:
            return

        data = dataframe.fillna("")
        item.update_content(data)
        uid = processor.blackboard.write(pipeline=self, item=item, processor=processor)\
"""


class GenericPipeline(IPipeline, Attribute, AuditLogger, ABC):
    _allowed: list

    def __init__(
        self,
        allowed: list = [],
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        *args,
        **kwargs,
    ):
        IPipeline.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler)
        self._allowed = allowed
        self.debug(msg="__init__", allowed=allowed)
        self.configure(**kwargs)

    def configure(self, **kwargs):
        self.debug(msg="configure", **kwargs)

        if not self.allowed(self._allowed, **kwargs):
            return

        for name, value in kwargs.items():
            if isinstance(value, (bool, dict, list, str)):
                self.push(name, value)
            else:
                error = f"Restricted type: {_NC(value)}.{name}. [bool, dict, list, str]"
                self.error(msg=error)
                raise AttributeError(error)

    @abstractmethod
    def process(self, processor: IProcessor, item, *args, **kwargs) -> None:
        self.evaluate(processor, IProcessor)
        if item is None:
            msg = f"{self.__class__.__name__}.process: Received None as item, cannot process."
            self.error(msg=msg)
            raise ValueError(msg)

        self.debug(
            msg="process",
            processor=processor.name,
            item=item.identifier if hasattr(item, "identifier") else "unknown",
            kwargs=kwargs,
        )
