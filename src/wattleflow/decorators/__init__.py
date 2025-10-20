# Module Name: decorators
# Description: This modul contains decorator classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

"""This module contains all Workflow decorators."""


from .classification import ClassificationDecorator
from .preset import PresetDecorator

__all__ = [
    "ClassificationDecorator",
    "PresetDecorator",
]
