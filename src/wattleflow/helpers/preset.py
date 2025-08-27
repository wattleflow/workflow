# Module Name: helpers/preset.py
# Description: This modul contains preset helper class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

from enum import Enum
from typing import Any, Optional, Type
from wattleflow.core import IWattleflow
from wattleflow.constants import Event
from wattleflow.helpers.attribute import MissingAttribute


PERMITED_TYPES = (bool, dict, list, int, float, str, Enum)


class Preset:
    def configure(
        self,
        caller: IWattleflow,
        permitted: Optional[list] = None,
        permitted_types: tuple = PERMITED_TYPES,
        raise_errors: bool = False,
        **kwargs: Any,
    ) -> None:
        def debug(msg: str, **kwargs):
            if hasattr(caller, "warning"):
                caller.debug(msg, **kwargs)  # type: ignore[attr-defined]

        def warning(msg: str, **kwargs):
            if hasattr(caller, "warning"):
                caller.warning(msg, **kwargs)  # type: ignore[attr-defined]

        debug(
            msg=Event.Configuring.value,
            caller=caller,
            permitted=permitted,
            permitted_types=permitted_types,
            raise_errors=raise_errors,
            **kwargs,
        )

        # no input values
        if not kwargs:
            msg = "No configuration values!"
            warning(msg=msg, **kwargs)  # type: ignore[attr-defined]
            return

        # allowed keys
        has_slots = hasattr(self, "__slots__") and bool(getattr(self, "__slots__"))
        if has_slots:
            allowed_keys = set(getattr(self, "__slots__"))
        elif permitted:
            allowed_keys = set(permitted)
        else:
            # fallback:allow only given keys
            allowed_keys = set(kwargs.keys())

        # setup attributes
        unknown_keys = []
        bad_types = []

        for key, val in kwargs.items():
            if key not in allowed_keys:
                unknown_keys.append(key)
                continue

            if not isinstance(val, permitted_types):
                bad_types.append((key, type(val).__name__))
                continue

            if hasattr(self, "push") and callable(getattr(self, "push")):
                getattr(self, "push")(key, val)  # type: ignore[attr-defined]
            else:
                setattr(self, key, val)

        # opctional raise error if something is not working
        if (unknown_keys or bad_types) and raise_errors:
            parts = []
            if unknown_keys:
                parts.append(f"Unknown keys: {', '.join(sorted(unknown_keys))}")

            if bad_types:
                parts.append(
                    "Restricted types: "
                    + ", ".join(f"{k}={t}" for k, t in bad_types)  # noqa: W503
                    + f". Allowed: {[t.__name__ for t in permitted_types]}"  # noqa: W503
                )
            raise ValueError("; ".join(parts))

        # log messages if not raising error
        if unknown_keys and hasattr(caller, "warning"):
            warning(msg=f"Ignored unknown keys: {', '.join(sorted(unknown_keys))}")

        if bad_types and hasattr(caller, "warning"):
            warning(
                msg=(
                    "Ignored keys with restricted types: "
                    + ", ".join(f"{k}({t})" for k, t in bad_types)  # noqa: W503
                )
            )

    def __getattr__(self, name: str) -> Any:
        # only when atribut ne exists; return None instead of exception.
        return None

    def to_dict(self) -> dict:
        result = {}
        if hasattr(self, "__slots__") and bool(getattr(self, "__slots__")):
            for key in getattr(self, "__slots__"):
                # getattr w defaultom None, avoiding __getattr__ petlju:
                try:
                    val = object.__getattribute__(self, key)
                except AttributeError:
                    val = None
                result[key] = val
        else:
            result.update(getattr(self, "__dict__", {}) or {})
        return result

    @staticmethod
    def convert(caller: object, name: str, cls: Type[Enum], dict_object: dict):
        if name not in dict_object:
            raise MissingAttribute(
                caller=caller, error="", name=name, cls=cls, dict_object=dict_object
            )

        value = dict_object[name]

        for enum_member in cls:
            if enum_member.name == value:
                dict_object[name] = enum_member
                return

        raise ValueError(f"Invalid enum value '{value}' for {cls.__name__}")
