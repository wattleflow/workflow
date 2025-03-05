# Module Name: core/concrete/pipeline.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete pipeline classes.

from abc import abstractmethod
from wattleflow.core import IProcessor
from wattleflow.core import IPipeline
from wattleflow.concrete.attribute import Attribute
from wattleflow.constants.enums import Event


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
    Processing Items (process)
        - Abstract method (@abstractmethod) ensures child classes must implement process().
        - Calls self.evaluate(processor, IIterator) to validate that processor is an IIterator.
"""


class GenericPipeline(IPipeline, Attribute):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.name = self.__class__.__name__

    def debug_log(self, processor, item):
        processor.audit(self, event=Event.DebugLog, item=item)

    @abstractmethod
    def process(self, processor, item, *args, **kwargs) -> None:
        self.evaluate(processor, IProcessor)
        if item is None:
            raise ValueError(
                f"{self.__class__.__name__}: Received None as item, cannot process."
            )

        self.debug_log(processor, item)
