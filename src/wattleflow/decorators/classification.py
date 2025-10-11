# Module Name: decorator/classification.py
# Description: This modul contains classification decorator class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

"""
Classification
    __slots__ = ("_classification", "_dlm")

    Constructor:
        def __init__(self, parent: IWattleflow, **kwargs):

    Properties:
        classification: Enum
        dlm: Enum
"""

from enum import Enum
import wattleflow.constants.enums as wattleconst
from wattleflow.core import IWattleflow


class ClassificationDecorator:
    __slots__ = ("_classification", "_dlm")

    def __init__(self, parent: IWattleflow, **kwargs):
        super().__init__()

        classification = kwargs.pop(
            "classification",
            wattleconst.Classification.UNCLASSIFIED,
        )

        dlm = kwargs.pop(
            "dlm",
            wattleconst.ClassificationDLM.UNCLASSIFIED,
        )

        self._classification: Enum = getattr(
            wattleconst,
            classification.upper(),
            wattleconst.Classification.UNCLASSIFIED,
        )

        self._dlm: Enum = getattr(
            wattleconst,
            dlm.upper(),
            wattleconst.ClassificationDLM.UNDEFINED,
        )

    @property
    def classification(self) -> Enum:
        return self._classification

    @property
    def dlm(self) -> Enum:
        return self._dlm
