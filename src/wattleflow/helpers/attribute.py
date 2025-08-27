# Module Name: helpers/attribute.py
# Description: This modul contains helpers attribute handling class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

import inspect
from enum import Enum
from typing import Any, Optional
from wattleflow.core import IWattleflow


class MissingAttribute(AttributeError):
    def __init__(self, caller: object, error: str, **kwargs):
        self._msg = f"{Attribute.class_name(caller)}.{error}"
        if kwargs:
            self._msg += f" {kwargs}"
        super().__init__(f"Attribute not found: [{self._msg}].")

    def __repr__(self) -> str:
        return f"{self.name}: {self._msg}"


class Attribute:
    @staticmethod
    def name(o: object) -> str:
        return getattr(o, "__name__", "<unknown>")

    @staticmethod
    def class_name(o: object) -> str:
        return getattr(getattr(o, "__class__", None), "__name__", "<None>")

    @staticmethod
    def type_name(o: object) -> str:
        return type(o).__name__

    @staticmethod
    def find_name_by_variable_old(obj):
        depth = 0
        frame = inspect.currentframe()
        while frame and depth < 5:
            for _, value in frame.f_back.f_locals.items():  # type: ignore
                if value is obj:
                    return value
            frame = frame.f_back
            depth += 1
        return None

    @staticmethod
    def find_name_by_variable(obj):
        return getattr(obj, "__name__", "Unknown")

    @staticmethod
    def find_object_by_name_old(name) -> Optional[object]:
        _locals = inspect.currentframe().f_back.f_locals  # type: ignore
        if name in _locals:
            return _locals[name]
        return None

    @staticmethod
    def find_object_by_name(obj):
        return getattr(obj, "__name__", "Unknown")

    @staticmethod
    def allowed(caller: object, allowed, **kwargs) -> bool:
        if allowed is None:
            return False

        Attribute.evaluate(caller, allowed, list)  # type: ignore

        if not len(allowed) > 0:
            return False

        restricted = set(kwargs.keys()) - set(allowed)

        if restricted:
            from wattleflow.helpers.functions import (
                _NC,
            )  # pylint: disable=import-outside-toplevel

            raise AttributeError(f"{_NC(caller)} - Restricted : [{restricted}]")

        return True

    @staticmethod
    def convert(caller: object, name: str, cls: type, **kwargs) -> Any:
        if name not in kwargs:
            raise MissingAttribute(caller, f"kwargs[{name}]")

        value = kwargs[name]

        if isinstance(cls, type) and issubclass(cls, Enum):
            for enum_member in cls:
                if value in (enum_member.name, enum_member.value):
                    kwargs[name] = enum_member
                    return
            expected = f"one of {[m.name for m in cls]}"
        else:
            if isinstance(value, cls):
                return
            try:
                kwargs[name] = cls(value)
                return
            except Exception:  # pylint: disable=broad-except
                expected = cls.__class__.__name__

        from wattleflow.helpers.functions import (
            _NC,
            _NT,
        )  # pylint: disable=import-outside-toplevel

        txt = "{}: unexpected type found [{}:{}] expected [{}]"
        error = txt.format(_NC(caller), value, _NT(value), expected)
        raise TypeError(error)

    @staticmethod
    def evaluate(caller: IWattleflow, target: object, expected_type: type):
        if not expected_type:
            return

        if target is expected_type:
            return

        varname = Attribute.find_name_by_variable(target)
        name = (
            target.__class__.__name__
            if hasattr(target, "__class__")
            else type(target).__name__
        )
        expected_name = expected_type.__name__
        owner = getattr(caller, "name", caller.__class__.__name__)

        if not isinstance(target, expected_type):
            error = f"{owner}.{varname}: found unexpected type [{name}], expected [{expected_name}]"  # noqa: E501
            raise TypeError(error)

    @staticmethod
    def exists(caller: object, name: str, cls: type):
        attr = getattr(caller, name, None)

        if not attr:
            raise MissingAttribute(caller, name)

        Attribute.evaluate(caller, attr, cls)  # type: ignore

    @staticmethod
    def load_from_class(name: str, obj: object, cls: type, **kwargs):
        if not isinstance(obj, str):
            raise TypeError(
                f"Expected class path as string for {name}, got {type(obj).__name__}"
            )

        from wattleflow.helpers.system import (
            ClassLoader,
        )  # pylint: disable=import-outside-toplevel

        try:
            instance = ClassLoader(obj, **kwargs).instance
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(f"Class {obj} not found in module.") from e
        except Exception as e:
            raise ValueError(f"Failed to instantiate {obj}: {e}") from e

        if not isinstance(instance, cls):
            raise TypeError(
                f"Loaded instance of {obj} is not a subclass of {cls.__name__}"
            )

        return instance

    @staticmethod
    def mandatory(caller: object, name: str, cls: type, **kwargs) -> bool:
        Attribute.evaluate(caller, kwargs, dict)  # type: ignore

        if name not in kwargs:
            raise MissingAttribute(caller, f"[{name}] not found in kwargs!")

        obj = kwargs.pop(name, None)

        if isinstance(obj, cls):
            setattr(caller, name, obj)
            return True

        if cls in [int, dict, str, tuple, list] or not isinstance(cls, IWattleflow):
            raise TypeError(
                f"Incorrect type for {name}: expected {cls}, found <{Attribute.class_name(obj)}>."
            )

        try:
            Attribute.load_from_class(name, obj, cls, **kwargs)
            return True
        except Exception as e:
            raise ValueError(f"Error loading class: kwargs[{name}]: {e}") from e

    @staticmethod
    def get(
        caller: IWattleflow,
        name: str,
        kwargs: dict,
        cls: Optional[type],
        mandatory=True,
    ) -> Optional[object]:
        if mandatory:
            if not kwargs:
                raise MissingAttribute(caller, "kwargs")

            if name not in kwargs:
                raise MissingAttribute(caller, f"kwargs[{name}]")

        item = kwargs.pop(name, None)

        if cls:
            if isinstance(item, cls):
                return item

        from wattleflow.helpers.system import (
            ClassLoader,
        )  # pylint: disable=import-outside-toplevel

        try:
            if mandatory:
                if isinstance(item, str):
                    instance = ClassLoader(item, **kwargs).instance
                    setattr(caller, name, instance)
                    return instance
                else:
                    raise MissingAttribute(caller, name)
        except Exception as e:
            raise MissingAttribute(caller, error=e) from e

    @staticmethod
    def optional(
        caller: object, name: str, cls: type, default: Optional[object], **kwargs
    ):
        if (not kwargs) and (not default):
            return

        if (name not in kwargs) and (not default):
            return

        instance = kwargs.pop(name, default)

        if not isinstance(instance, cls):
            instance = Attribute.load_from_class(name, instance, cls, **kwargs)

        if default:
            Attribute.evaluate(caller, instance, cls)  # type: ignore

        setattr(caller, name, instance)

    @staticmethod
    def get_attr(caller: object, name: str) -> Optional[object]:
        d = getattr(caller, "__dict__", None)
        if d is not None and name in d:
            return d[name]

        # Go through the MRO and check if the name is in __slots__
        for cls in type(caller).__mro__:
            slots = cls.__dict__.get("__slots__")
            if not slots:
                continue
            if isinstance(slots, str):
                slots = (slots,)
            if name in slots:
                # if exists, try to get it - can still throw AttributeError if unallocated.
                return object.__getattribute__(caller, name)

        # if in neither throw AttributeError w !r - adds quote as the value is string Litteral
        # error = f"({type(caller).__name__!s}) has no attribute {name!r}"
        error = f"{name!r} is missing attribute!"
        raise MissingAttribute(caller=caller, error=error, name=name)

    # def __str__(self):
    #     attributes = ""
    #     for k, v in self.__dict__.items():
    #         attributes += f"{k}:{v}\n"
    #     return attributes
