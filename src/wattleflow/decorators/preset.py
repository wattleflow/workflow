# Module name: preset.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
PresetDecorator
    __slots__ = ("_allowed", "_values", "_parent")
    __init__(parent: IWattleflow, **kwargs)

When using PresetDecorator you must add following in the instantiating parent class,
to process assigned atributes.

# Must be implemented if using PresetDecorator
def __getattr__(self, name: str) -> Any:
    preset: PresetDecorator = object.__getattribute__(self, "_preset")
    return preset.__getattr__(name)
"""

from __future__ import annotations
from typing import Any
from wattleflow.core import IWattleflow
from wattleflow.concrete.exception import AttributeException


class PresetDecorator:
    __slots__ = ("_allowed", "_values", "_parent")

    def __init__(self, parent: IWattleflow, **kwargs):
        self._parent: IWattleflow = parent

        allowed = kwargs.pop("allowed", [])
        assert isinstance(allowed, list), (
            f"{parent.__class__.__name__}.allowed must be [list]!"
        )

        if isinstance(allowed, dict):
            allowed_set = set(allowed)
        elif allowed is None:
            allowed_set = set()
        else:
            try:
                allowed_set = set(allowed)
            except TypeError as e:
                raise TypeError(
                    "alloweed attribute must have iterable elements/names"
                ) from e

        object.__setattr__(self, "_allowed", allowed_set)
        values = {k: v for k, v in kwargs.items() if k in allowed_set}
        object.__setattr__(self, "_values", values)

    def __getattr__(self, name: str) -> Any:
        try:
            return object.__getattribute__(self._parent, name)
        except AttributeError:
            pass

        if name in self._allowed:
            return self._values.get(name, None)

        try:
            parent_name = object.__getattribute__(self._parent, "name")
        except AttributeError:
            parent_name = type(self._parent).__name__

        raise AttributeException(
            caller=self._parent,
            error=f"{parent_name}.{name} is not permitted.",
            name=name,
            exc_info=True,
        )

    def __setattr__(self, name: str, value: Any):
        if name in PresetDecorator.__slots__:
            object.__setattr__(self, name, value)
        elif name in self._allowed:
            self._values[name] = value
        else:
            raise AttributeError(f"{self._parent.name}.{name} is not permitted.")

    def __delattr__(self, name: str):
        if name in self._values:
            del self._values[name]
        else:
            raise AttributeError(
                f"{self._parent.name}.{name} attribute does not exists!"
            )

    def __repr__(self) -> str:
        size: int = len(self._values) if hasattr(self, "_values") else 0
        return f"{self._parent.name}:elements:[{size}]"
