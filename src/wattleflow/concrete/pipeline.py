# Module name: concrete/pipeline.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
from abc import ABC, abstractmethod
from logging import Handler, NOTSET
from typing import Any, Optional
from wattleflow.core import IProcessor, IPipeline, ITarget
from wattleflow.concrete.wattleflow import Wattleflow
from wattleflow.concrete.exception import AuditException
from wattleflow.constants import Event
from wattleflow.decorators.preset import PresetDecorator

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class PipelineError(AuditException):
    pass


# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Pipelines                                                            #
# --------------------------------------------------------------------------- #


class GenericPipeline(Wattleflow, IPipeline, ABC):
    def __init__(
        self,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        **kwargs,
    ):
        super().__init__(level=level, handler=handler)

        self.debug(
            msg=Event.Constructor.name,
            level=level,
            handler=handler,
            **kwargs,
        )

        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

    # region Private
    def __del__(self):
        if self._preset:
            try:
                del self._preset
            except Exception as e:
                reason = (
                    "Destructor %s.__del__ error: %s" % self.__class__.__name__,
                    str(e),
                )
                self.error(
                    msg=Event.Delete.name,
                    preset=self._preset,
                    reason=reason,
                )

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}"

    # endregion

    @abstractmethod
    def transform(
        self,
        processor: IProcessor,
        facade: ITarget,
        **kwargs,
    ) -> Any: ...

    def process(
        self,
        processor: IProcessor,
        facade: ITarget,
        **kwargs,
    ) -> None:
        self.debug(
            msg=Event.Process.name,
            step=Event.Starting.name,
            processor=processor,
            facade=facade,
        )
        result = None
        try:
            assert isinstance(processor, IProcessor), "Expected IProcessor. Found %s" % type(
                processor
            )
            assert isinstance(facade, ITarget), "Expected ITarget. Found %s" % type(facade)
            self.transform(processor, facade, **kwargs)
        except AssertionError as e:
            self.error(msg=Event.Process.name, step=Event.Failed.name, error=str(e))
            raise PipelineError(str(e)) from e
        except Exception as e:
            error = "%s.process error: %s" % (self.__class__.__name__, str(e))
            self.error(msg=Event.Process.name, step=Event.Failed.name, reason=error)
            raise PipelineError(
                caller=self,
                error=error,
                # trace=traceback.format_exc(),
            ) from e
        finally:
            self.debug(
                msg=Event.Process.name,
                step=Event.Completed.name,
                result=result,
            )


# --------------------------------------------------------------------------- #
# endregion Pipelines                                                         #
# --------------------------------------------------------------------------- #
