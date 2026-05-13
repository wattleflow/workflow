# Module name: decorators/preset.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
This module provides PresetDecorator, a lightweight attribute extension helper for
Wattleflow components. It lets a parent object expose a controlled set of optional
runtime attributes while preserving strict access rules for unsupported names.
In conjunction with classes such as Blackboard, Managers, Drivers, and Processors,
PresetDecorator keeps configurable object state explicit, bounded, and discoverable
across the wattleflow-workflow runtime.

Parent classes using PresetDecorator must delegate missing attribute lookups through
their own __getattr__ implementation:

    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)
"""

from __future__ import annotations
from typing import Any
from wattleflow.core import IWattleflow


class PresetDecorator:
    __slots__ = ("_allowed", "_values", "_parent")

    def __init__(self, parent: IWattleflow, **kwargs):
        self._parent: IWattleflow = parent

        allowed = kwargs.pop("allowed", [])
        if not isinstance(allowed, list):
            raise TypeError(f"{parent.__class__.__name__}.allowed must be a list")

        allowed_set = set(allowed)
        object.__setattr__(self, "_allowed", allowed_set)
        values = {k: v for k, v in kwargs.items() if k in allowed_set}
        object.__setattr__(self, "_values", values)

    def __del__(self) -> None:
        try:
            self._values.clear()
            self._parent = None
        except Exception:
            pass

    def __delattr__(self, name: str):
        if name in self._values:
            del self._values[name]
        else:
            parent_name = getattr(self._parent, "name", type(self._parent).__name__)
            raise AttributeError(f"{parent_name}.{name} attribute does not exist!")

    def __getattr__(self, name: str) -> Any:
        try:
            return object.__getattribute__(self._parent, name)
        except AttributeError:
            pass

        if name in self._allowed:
            return self._values.get(name, None)

        parent_name = getattr(self._parent, "name", type(self._parent).__name__)
        raise AttributeError(f"{parent_name}.{name} is not permitted.")

    def __setattr__(self, name: str, value: Any):
        if name in PresetDecorator.__slots__:
            object.__setattr__(self, name, value)
        elif name in self._allowed:
            self._values[name] = value
        else:
            parent_name = getattr(self._parent, "name", type(self._parent).__name__)
            raise AttributeError(f"{parent_name}.{name} is not permitted.")

    def __repr__(self) -> str:
        size: int = len(self._values) if hasattr(self, "_values") else 0
        parent_name = getattr(self._parent, "name", type(self._parent).__name__)
        return f"{parent_name}:elements:[{size}]"
