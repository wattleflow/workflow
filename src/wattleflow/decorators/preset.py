# Module name: decorators/preset.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations
from typing import Any, ClassVar, Iterable
from wattleflow.core import IWattleflow


# NFR-ORG-05: declaration resolution and the unknown-key report are one class
# holding its own constants; PresetDecorator only wires them.
class PresetGate:
    """Mechanics behind `PresetDecorator`: which keys are permitted, and what to
    do with the ones that are not."""

    DECLARATION: ClassVar[str] = "ALLOWED"

    # Consumed by the framework itself (Audit pops these from its own copy of
    # kwargs), so they reach the preset and are never a configuration mistake.
    FRAMEWORK: ClassVar[frozenset[str]] = frozenset(
        {"allowed", "formating", "formatting", "handler", "level", "name"}
    )

    @classmethod
    def resolve(cls, target: type, override: Any = None) -> set[str]:
        """Permitted keys for a class.

        The class attribute is the declaration, an explicit `allowed=` is the
        exception (NFR-ORG-07). Without an override the declaration is UNIONED
        across the MRO, so a subclass declares only what it adds and never has
        to name its parent.
        """
        if override is None:
            merged: set[str] = set()
            for klass in target.__mro__:
                merged.update(vars(klass).get(cls.DECLARATION, ()) or ())
            return merged
        if isinstance(override, (tuple, set, frozenset)):
            override = list(override)
        if not isinstance(override, list):
            raise TypeError(f"{target.__name__}.allowed must be a list")
        return set(override)

    @classmethod
    def report_unknown(cls, parent: IWattleflow, keys: Iterable[str], allowed: set[str]) -> None:
        """Warn about keys the preset is about to drop.

        A key that is neither declared nor consumed by the framework is a
        configuration mistake — a typo or a block pasted from another component.
        Dropping it silently is what made such mistakes invisible.
        """
        unknown = sorted(k for k in keys if k not in allowed and k not in cls.FRAMEWORK)
        if not unknown or not hasattr(parent, "warning"):
            return
        parent.warning(
            msg="preset",
            reason="keys are not declared in ALLOWED and were discarded",
            discarded=unknown,
        )


class PresetDecorator:
    # NFR-ORG-07: the permitted keys are declared by the configured class in a
    # class attribute named exactly `ALLOWED`, and resolved by PresetGate — a
    # subclass never has to pass `allowed=` up the constructor chain.
    DECLARATION = PresetGate.DECLARATION

    __slots__ = ("_allowed", "_values", "_parent")

    def __init__(self, parent: IWattleflow, **kwargs):
        self._parent: IWattleflow = parent

        allowed_set = PresetGate.resolve(type(parent), kwargs.pop("allowed", None))
        PresetGate.report_unknown(parent, kwargs, allowed_set)

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
    "PresetGate",
]
