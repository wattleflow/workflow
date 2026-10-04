# Module name: concrete/helpers.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from enum import Enum
from importlib import import_module
from pathlib import Path
from typing import Any
from wattleflow.core import IWattleflow
from wattleflow.concrete.exception import AttributeException

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Private helpers                                                      #
# --------------------------------------------------------------------------- #

# Types that are never loaded from a class path given as a string.
_PRIMITIVES = (int, float, bool, bytes, dict, list, set, frozenset, str, tuple)

# Keyword names used by AttributeException / load_from_class themselves.
# Caller kwargs with these names are dropped from the error context, otherwise
# they would collide with explicit keyword arguments (TypeError).
_RESERVED = frozenset({"caller", "error", "name", "cls", "obj"})


def _extra(kwargs: dict) -> dict:
    """kwargs without names that collide with explicit keyword arguments."""
    return {k: v for k, v in kwargs.items() if k not in _RESERVED}


# --------------------------------------------------------------------------- #
# endregion Private helpers                                                   #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class Attribute:
    """Attribute validation and conversion helpers.

    Conventions (same for all methods):
      * convert() returns the converted value; the caller assigns it.
      * mandatory() and optional() take **kwargs, so they never change the
        caller's dictionary. Both set the resolved value on `caller`.
      * get() takes an explicit dict and consumes `name` from it; it sets a
        value it had to load on `caller` and returns the value.
      * A value of the wrong type always raises AttributeException.
      * A string is a class path (loaded through ClassLoader) only where a
        class is expected: the class is resolved and checked against the
        expected type BEFORE it is instantiated. mandatory() loads only for
        IWattleflow types; with no expected type a value is returned as it is.
    """

    # --- name helpers: thin wrappers over NameHelper (single source) ------- #

    @staticmethod
    def name(o: object) -> str:
        return NameHelper.obj_name(o) or "<unknown>"

    @staticmethod
    def class_name(o: object) -> str:
        return NameHelper.cls_name(o) or "<None>"

    @staticmethod
    def type_name(o: object) -> str:
        return NameHelper.typ_name(o)

    @staticmethod
    def find_name_by_variable(obj):
        """Class name of obj; bypasses a facade's overridden attribute access."""
        cls = object.__getattribute__(obj, "__class__")
        return object.__getattribute__(cls, "__name__")

    @staticmethod
    def find_object_by_name(obj):
        return NameHelper.obj_name(obj) or "Unknown"

    # --- validation -------------------------------------------------------- #

    @classmethod
    def evaluate(
        cls,
        caller: IWattleflow,
        target: object,
        expected_type: type,
    ):
        if not expected_type:
            return

        if isinstance(target, expected_type):
            return

        name = cls.find_name_by_variable(target)
        expected_name = getattr(expected_type, "__name__", repr(expected_type))
        error = (
            f"{NameHelper.owner(caller)!r}: Unexpected type: "
            f"Found {name!r} instead of {expected_name!r}."
        )
        raise AttributeException(
            caller=caller,
            error=error,
            target=target,
            expected_type=expected_type,
        )

    @classmethod
    def allowed(cls, caller: object, allowed, **kwargs) -> bool:
        """Check kwargs against a whitelist.

        None  -> no whitelist defined, returns False.
        []    -> explicit empty whitelist: any kwarg is restricted.
        Raises AttributeException for names outside the whitelist.
        """
        if allowed is None:
            return False

        cls.evaluate(caller, allowed, list)

        restricted = set(kwargs.keys()) - set(allowed)

        if restricted:
            raise AttributeException(
                caller=caller,
                error=f"Restricted: {restricted!r}",
            )

        return True

    @staticmethod
    def exists(caller: object, name: str, cls: type):
        if not isinstance(caller, IWattleflow):
            raise AttributeException(
                None,
                "The `caller` must be from a Wattleflow family!",
                True,
            )

        attr = getattr(caller, name, None)

        if attr is None:
            raise AttributeException(caller=caller, error=name)  # type: ignore

        Attribute.evaluate(caller, attr, cls)  # type: ignore

    # --- conversion -------------------------------------------------------- #

    @staticmethod
    def convert(caller: object, name: str, cls: type, **kwargs) -> Any:
        """Return kwargs[name] converted to cls (Enum members by name or value)."""
        if name not in kwargs:
            raise AttributeException(caller=caller, error=f"kwargs[{name}]")

        value = kwargs[name]

        if isinstance(value, cls):
            return value

        if isinstance(cls, type) and issubclass(cls, Enum):
            for member in cls:
                if value in (member.name, member.value):
                    return member
            expected = f"one of {[m.name for m in cls]}"
        else:
            try:
                return cls(value)
            except Exception:  # pylint: disable=broad-except
                expected = cls.__name__

        txt = "{}: unexpected type found [{}:{}] expected [{}]"
        error = txt.format(NameHelper.nc(caller), value, NameHelper.nt(value), expected)

        raise AttributeException(
            caller=caller,  # type: ignore
            error=error,
            name=name,
            cls=cls,
            **_extra(kwargs),
        )

    # --- loading / resolving ----------------------------------------------- #

    @staticmethod
    def _class_at(path: str) -> object:
        """The object a class path names, without instantiating it."""
        module_path, _, class_name = path.rpartition(".")
        if not module_path:
            raise ValueError(f"Invalid class path: {path}")
        module = import_module(module_path)
        if not hasattr(module, class_name):
            raise AttributeError(f"Class '{class_name}' not found in module '{module_path}'")
        return getattr(module, class_name)

    @staticmethod
    def load_from_class(
        name: str, obj: object, cls: type, caller: object = None, **kwargs
    ):
        if not isinstance(obj, str):
            raise TypeError(
                f"Expected class path as string for {name}, got {type(obj).__name__}"
            )

        # NOTE: local import keeps the static import graph free of the
        # concrete -> helpers edge, but the runtime dependency remains.
        from wattleflow.helpers.system import (
            ClassLoader,
        )  # pylint: disable=import-outside-toplevel

        # v0.0.1.23: DEF-HLP-02, the class is resolved and checked BEFORE it is instantiated, so
        # a class of the wrong type never runs its constructor
        try:
            klass = Attribute._class_at(obj)
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(
                f"Class {obj!r} could not be loaded: module {e.name!r} not found."
            ) from e
        except Exception as e:
            raise ValueError(f"Failed to load {obj}: {e}") from e

        if not (isinstance(klass, type) and issubclass(klass, cls)):
            error = f"Loaded class {obj} is not a subclass of {cls.__name__}"
            raise AttributeException(
                caller=caller,
                error=error,
                name=name,
                obj=obj,
                cls=cls,
                **_extra(kwargs),
            )

        try:
            return ClassLoader(obj, **kwargs).instance
        except Exception as e:
            raise ValueError(f"Failed to instantiate {obj}: {e}") from e

    # v0.0.1.23: DEF-HLP-03, private and without a `cls` parameter, so it goes through `cls`; the public
    # methods keep `cls` as the domain type and stay static (NFRQ-ORG-05 exception c.1, deferred)
    @classmethod
    def _resolve(
        cls,
        caller: object,
        name: str,
        value: object,
        expected: type | None,
        params: dict,
        load: bool = True,
    ) -> object:
        """Return value as an instance of `expected`.

        An instance of `expected` is returned unchanged, and so is any value when
        nothing is expected. A string is loaded as a class path (with `params` as
        constructor arguments) when `load` allows it and `expected` is not a
        primitive; anything else is an incorrect type.
        """
        if expected is None or isinstance(value, expected):
            return value

        if load and isinstance(value, str) and expected not in _PRIMITIVES:
            try:
                return cls.load_from_class(
                    name,
                    value,
                    expected,
                    caller=caller,
                    **_extra(params),
                )
            except AttributeException:
                raise
            except Exception as e:
                raise AttributeException(
                    caller=caller,
                    error=f"Error loading class: kwargs[{name!r}]: {e}",
                    name=name,
                    cls=expected,
                    **_extra(params),
                ) from e

        raise AttributeException(
            caller=caller,
            error=f"Incorrect type {name!r}:"
            f" expected {expected!r},"
            f" found <{cls.class_name(value)!r}>.",
            name=name,
            cls=expected,
            **_extra(params),
        )

    @staticmethod
    def _is_family(cls: object) -> bool:
        return isinstance(cls, type) and issubclass(cls, IWattleflow)

    @staticmethod
    def mandatory(caller: object, name: str, cls: type, **kwargs) -> bool:
        if name not in kwargs:
            raise AttributeException(
                caller=caller,
                error=f"{NameHelper.owner(caller)!r}: Mandatory value {name!r} not found in kwargs!",  # noqa: E501
                name=name,
                cls=cls,
                **_extra(kwargs),
            )

        rest = {k: v for k, v in kwargs.items() if k != name}
        # a class path is loaded only for IWattleflow types: a string from configuration may not
        # make an arbitrary module import for any other type
        instance = Attribute._resolve(
            caller, name, kwargs[name], cls, rest, load=Attribute._is_family(cls)
        )
        setattr(caller, name, instance)
        return True

    @staticmethod
    def get(
        caller: IWattleflow,
        name: str,
        kwargs: dict,
        cls: type | None,
        mandatory=True,
    ) -> object | None:
        if not kwargs or name not in kwargs:
            if mandatory:
                raise AttributeException(
                    caller=caller,
                    error=f"kwargs[{name}]",
                    kwargs=kwargs,
                    cls=cls,
                    mandatory=mandatory,
                )
            return None

        item = kwargs.pop(name)

        if item is None:
            if mandatory:
                raise AttributeException(
                    caller=caller,
                    error=f"kwargs[{name}] is None",
                    cls=cls,
                    mandatory=mandatory,
                )
            return None

        instance = Attribute._resolve(caller, name, item, cls, kwargs)
        if instance is not item:
            setattr(caller, name, instance)  # a value that was loaded is kept on the caller
        return instance

    @staticmethod
    def optional(
        caller: object, name: str, cls: type, default: object | None, **kwargs
    ):
        value = kwargs.get(name)

        if value is None:
            value = default

        if value is None:
            return None

        rest = {k: v for k, v in kwargs.items() if k != name}
        instance = Attribute._resolve(caller, name, value, cls, rest)
        setattr(caller, name, instance)
        return instance

    @staticmethod
    def get_attr(caller: object, name: str) -> object | None:
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
                # if exists, try to get it - can still throw AttributeError
                # if the slot is unallocated.
                return object.__getattribute__(caller, name)

        error = f"{caller!r} is missing attribute {name!r}."
        raise AttributeException(caller=caller, error=error)


class NameHelper:
    """Concrete-local object-name primitives.

    A domain-local copy of the helpers.functions trio, so concrete/ need not import
    back into wattleflow.helpers — that reverse edge is what turns helpers→concrete
    into an ORG-01 cycle.
    """

    @staticmethod
    def obj_name(o):
        """__name__ of a class/function/module, else None."""
        return getattr(o, "__name__", None)

    @staticmethod
    def cls_name(o):
        """__class__.__name__ if present, else None."""
        return getattr(getattr(o, "__class__", None), "__name__", None)

    @staticmethod
    def typ_name(o) -> str:
        """type(o).__name__ — always a string."""
        return type(o).__name__

    @staticmethod
    def owner(o) -> str:
        """Display name of o: its `name` attribute, else its class name.

        Never raises: it is used while building error messages.
        """
        try:
            return getattr(o, "name", None) or type(o).__name__
        except Exception:  # pylint: disable=broad-except
            return type(o).__name__

    @staticmethod
    def source_name(o) -> str | None:
        """Human-readable name of the unit behind a facade, or None.

        Never raises: it runs inside audit records, where an exception would mask
        the event being reported. A facade forwards unknown attributes to its
        adaptee, so a document type without a filename simply yields None.
        """
        try:
            name = getattr(o, "filename", None)
        except Exception:
            return None
        return Path(str(name)).name if name else None

    @staticmethod
    def _members(o) -> dict:
        """Instance attributes from __dict__ and from __slots__ (all classes)."""
        result = dict(getattr(o, "__dict__", {}))

        for klass in type(o).__mro__:
            slots = klass.__dict__.get("__slots__")
            if not slots:
                continue
            if isinstance(slots, str):
                slots = (slots,)
            for slot in slots:
                if slot in ("__dict__", "__weakref__") or slot in result:
                    continue
                try:
                    result[slot] = object.__getattribute__(o, slot)
                except AttributeError:
                    pass  # unallocated slot

        return result

    @staticmethod
    def _is_dunder(name: str) -> bool:
        return name.startswith("_") and name.endswith("_")

    @classmethod
    def print_all(cls, o) -> None:
        """Print all attributes (including private/protected)."""
        for k, v in cls._members(o).items():
            print(f"{k}: {v}")

    @classmethod
    def list_vars(cls, o):
        """
        Return a list of instance variable names excluding
        names that start AND end with an underscore.
        """
        return [n for n in cls._members(o) if not cls._is_dunder(n)]

    @classmethod
    def list_dir(cls, o):
        """
        Return a list of names from dir(o) excluding
        names that start AND end with an underscore.
        """
        return [n for n in dir(o) if not cls._is_dunder(n)]

    @classmethod
    def print_prop(cls, o) -> None:
        """
        Print public/protected properties (skip names starting and ending with '_').
        """
        for k, v in cls._members(o).items():
            if not cls._is_dunder(k):
                print(f"{k}: {v}")

    @classmethod
    def name(cls, o):
        return cls.obj_name(o)

    @classmethod
    def nc(cls, o):
        return cls.cls_name(o)

    @classmethod
    def nt(cls, o) -> str:
        return cls.typ_name(o)


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #


__all__ = ["Attribute", "NameHelper"]
