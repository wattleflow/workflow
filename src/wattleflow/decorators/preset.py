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

        allowed = kwargs.pop("allowed", ())

        if isinstance(allowed, dict):
            allowed_set = set(allowed)
        elif isinstance(allowed, dict):
            allowed_set = set(allowed.keys())
        elif allowed is None:
            allowed_set = set()
        else:
            try:
                allowed_set = set(allowed)
            except TypeError:
                raise TypeError("alloweed attribute must have iterable elements/names")

        object.__setattr__(self, "_allowed", allowed_set)
        values = {k: v for k, v in kwargs.items() if k in allowed_set}
        object.__setattr__(self, "_values", values)

    def __getattr__(self, name: str) -> Any:
        try:
            value = object.__getattribute__(self._parent, name)
            if value:
                return value
        except Exception:
            pass

        if name in self._allowed:
            return self._values.get(name, None)

        raise AttributeException(
            caller=self._parent,
            error=f"{self._parent.name}.{name} is not permitted.",
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
        return f"{self._parent.name}._preset"
