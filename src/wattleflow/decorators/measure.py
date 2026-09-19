# Module name: decorators/measure.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# Retired 2026-09-17 (DR-WFL-031 v3): measurement observes audit records instead of
# wrapping operations. The module is kept commented out for the record; nothing imports it.
# """`measured` — the class decorator that places a class under `Monitor` (v0.0.1.14).
#
# The measured methods are the operations the role's core interface declares, so
# a decorated base measures every subclass: an override is wrapped when the
# subclass is created. A class adds its own operations by naming them, e.g. a
# driver whose strategies call `copy` rather than `write`.
# """
#
# # --------------------------------------------------------------------------- #
# # region Imports                                                              #
# # --------------------------------------------------------------------------- #
# from __future__ import annotations
# import functools
# import inspect
# from typing import Any, Callable, ClassVar, Iterable
# from wattleflow.core import IBlackboard, IDriver, IPipeline, IProcessor, IRepository, IStrategy
# from wattleflow.helpers.monitor import Monitor
# # --------------------------------------------------------------------------- #
# # endregion Imports                                                           #
# # --------------------------------------------------------------------------- #
#
# __all__ = ["MeasuredMethods", "measured"]
#
#
# class MeasuredMethods:
#     """Which methods of a class are measured, and the wrapping that measures them."""
#
#     #: Role -> the operations its interface declares. `flush` is the blackboard's
#     #: unit-of-work write; it is concrete-only, but it is where the storage time goes.
#     ROLES: ClassVar[tuple[tuple[type, tuple[str, ...]], ...]] = (
#         (IProcessor, ("start",)),
#         (IPipeline, ("process",)),
#         (IBlackboard, ("create", "write", "flush")),
#         (IRepository, ("read", "write")),
#         (IStrategy, ("execute",)),
#         (IDriver, ("load", "close", "read", "write")),
#     )
#     DECLARED: ClassVar[str] = "__measured__"
#     PASS: ClassVar[str] = "__measured_pass__"
#     MARK: ClassVar[str] = "__wf_measured__"
#
#     @classmethod
#     def _union(cls, target: type, attribute: str) -> frozenset[str]:
#         names: set[str] = set()
#         for klass in target.__mro__:
#             names.update(vars(klass).get(attribute, ()))
#         return frozenset(names)
#
#     @classmethod
#     def roles(cls, target: type) -> tuple[str, ...]:
#         names: list[str] = []
#         for interface, methods in cls.ROLES:
#             if issubclass(target, interface):
#                 names.extend(methods)
#         return tuple(names)
#
#     @classmethod
#     def declare(cls, target: type, methods: Iterable[str], passes: Iterable[str]) -> None:
#         setattr(target, cls.DECLARED, frozenset((*cls.roles(target), *methods, *passes)))
#         setattr(target, cls.PASS, frozenset(passes))
#         cls._inject(target)
#         cls._propagate(target)
#         cls.wrap(target)
#
#     @classmethod
#     def wrap(cls, target: type) -> None:
#         passes = cls._union(target, cls.PASS)
#         for name in cls._union(target, cls.DECLARED):
#             original = vars(target).get(name)
#             if original is None or getattr(original, cls.MARK, False):
#                 continue
#             wrapper = cls._wrapper(original, name, name in passes)
#             if wrapper is not original:
#                 setattr(target, name, wrapper)
#
#     @classmethod
#     def _wrapper(cls, original: Any, name: str, is_pass: bool) -> Any:
#         function = getattr(original, "func", original)  # singledispatchmethod
#         if (
#             isinstance(original, (staticmethod, classmethod, property))
#             or not callable(function)
#             or getattr(function, "__isabstractmethod__", False)
#             # A generator's work happens in the caller's loop, interleaved with
#             # other spans; timing the call would measure only its creation.
#             or inspect.isgeneratorfunction(function)
#         ):
#             return original
#
#         @functools.wraps(function)
#         def measured_call(self: Any, *args: Any, **kwargs: Any) -> Any:
#             monitor = Monitor.active()
#             opens = is_pass and not monitor.running
#             if opens:
#                 paths = getattr(self, "measured_paths", None)
#                 monitor.begin(paths() if callable(paths) else ())
#             frame = monitor.enter(self, name)
#             failed = True
#             try:
#                 result = original.__get__(self, type(self))(*args, **kwargs)
#                 failed = False
#                 return result
#             finally:
#                 monitor.leave(frame, failed)
#                 if opens:
#                     monitor.end()
#
#         setattr(measured_call, cls.MARK, True)
#         return measured_call
#
#     @classmethod
#     def _inject(cls, target: type) -> None:
#         def measure_units(self: Any, **units: Any) -> None:
#             """State the units this operation moved (`Measure` field names)."""
#             Monitor.active().units(self, **units)
#
#         def measure_boundary(self: Any, name: str) -> None:
#             """Mark the end of a unit of work; resources are sampled here."""
#             Monitor.active().boundary(name)
#
#         for function in (measure_units, measure_boundary):
#             if not hasattr(target, function.__name__):
#                 setattr(target, function.__name__, function)
#
#     @classmethod
#     def _propagate(cls, target: type) -> None:
#         if getattr(getattr(target, "__init_subclass__", None), cls.MARK, False):
#             return
#         previous = vars(target).get("__init_subclass__")
#
#         def __init_subclass__(sub: type, **kwargs: Any) -> None:
#             if previous is not None:
#                 previous.__func__(sub, **kwargs)
#             else:
#                 super(target, sub).__init_subclass__(**kwargs)
#             cls.wrap(sub)
#
#         setattr(__init_subclass__, cls.MARK, True)
#         target.__init_subclass__ = classmethod(__init_subclass__)  # type: ignore[assignment]
#
#
# def measured(*methods: str, passes: Iterable[str] = ()) -> Callable[[type], type]:
#     """Measure the role's interface operations, plus `methods`; `passes` open and
#     close a measured pass whose summary is written at INFO."""
#
#     def decorate(target: type) -> type:
#         MeasuredMethods.declare(target, methods, tuple(passes))
#         return target
#
#     return decorate
