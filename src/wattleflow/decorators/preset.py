# Module name: decorators/preset.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations
from typing import Any
from wattleflow.core import IWattleflow


class PresetDecorator:
    # NFR-ORG-07: the permitted keys are declared by the configured class in a
    # class attribute named exactly `ALLOWED`, and resolved HERE — a subclass
    # never has to pass `allowed=` up the constructor chain. An explicit
    # `allowed=` remains legal as a per-instance override; the class attribute
    # is the declaration, the argument is the exception.
    DECLARATION = "ALLOWED"

    __slots__ = ("_allowed", "_values", "_parent")

    def __init__(self, parent: IWattleflow, **kwargs):
        self._parent: IWattleflow = parent

        allowed = kwargs.pop("allowed", None)
        if allowed is None:
            allowed = getattr(type(parent), self.DECLARATION, [])
        if isinstance(allowed, tuple):
            allowed = list(allowed)
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


__all__ = [
    "PresetDecorator",
]
