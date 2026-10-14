# Module name: concrete/loader.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["ClassLoader"]

from importlib import import_module
from logging import NOTSET, Handler
from wattleflow.concrete.base import Wattleflow
from wattleflow.enums.event import Event
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class ClassLoader(Wattleflow):
    __slots__ = ("cls", "instance")

    def __init__(
        self,
        class_path: str,
        *args,
        **kwargs,
    ):

        level: int | str = kwargs.pop("level", NOTSET)
        handler: Handler | None = kwargs.pop("handler", None)

        super().__init__(**({"level": level} if level else {}), handler=handler)

        self.debug(
            msg=Event.Constructor,
            step=Event.Started,
            class_path=class_path,
        )

        module_path, _, class_name = class_path.rpartition(".")
        if not module_path:
            error = f"Invalid class path: {class_path}"
            self.debug(msg=Event.Constructor, step=Event.Failed, error=error)
            raise ValueError(error)

        try:
            module = import_module(module_path)
        except ModuleNotFoundError as e:
            self.debug(
                msg=Event.Constructor,
                step=Event.Failed,
                component=module_path,
                error=str(e),
            )
            raise

        if not hasattr(module, class_name):
            error = f"Class '{class_name}' not found in module '{module_path}'"
            self.debug(msg=Event.Constructor, step=Event.Failed, error=error)
            raise AttributeError(error)

        cls = getattr(module, class_name)
        self.cls = cls

        self.debug(
            msg=Event.Constructor,
            step=Event.Validating,
            component=module_path,
            target=class_name,
        )

        try:
            self.instance = cls(*args, **kwargs)
        except Exception as e:
            self.debug(
                msg=Event.Constructor,
                step=Event.Failed,
                target=class_name,
                error=str(e),
            )
            raise

        self.debug(
            msg=Event.Constructor,
            step=Event.Completed,
            target=cls.__name__,
        )

    @property
    def name(self) -> str:
        return type(self).__name__


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
