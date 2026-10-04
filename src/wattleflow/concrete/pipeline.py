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
from typing import Any
from wattleflow.core import IProcessor, IPipeline, ITarget
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.exception import PipelineException
from wattleflow.concrete.helpers import NameHelper
from wattleflow.enums.event import Event
from wattleflow.decorators.preset import PresetDecorator


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class PipelineError(PipelineException):
    """What a pipeline raises; one family with the PipelineException the processor raises."""


# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Pipelines                                                            #
# --------------------------------------------------------------------------- #


# @measured()
class GenericPipeline(Wattleflow, IPipeline, ABC):
    __slots__ = ("_preset",)

    def __init__(
        self,
        level: int = NOTSET,
        handler: Handler | None = None,
        **kwargs,
    ):
        super().__init__(level=level, handler=handler, **kwargs)

        self.debug(
            msg=Event.Constructor,
            level=level,
            handler=handler,
            kwargs=kwargs,
        )

        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

    # region Private
    def __del__(self):
        # A construction that failed before `_preset` was set has nothing to release.
        try:
            object.__getattribute__(self, "_preset")
        except AttributeError:
            return
        try:
            del self._preset
        except Exception as e:
            reason = "%s.__del__ error: %s" % (self.__class__.__name__, str(e))
            self.error(
                msg=Event.Delete,
                step=Event.Failed,
                reason=reason,
            )

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        # Before `_preset` exists the lookup answers with the name asked for, not with `_preset`.
        try:
            preset: PresetDecorator = object.__getattribute__(self, "_preset")
        except AttributeError:
            raise AttributeError(name) from None
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
        # v0.0.1.14: no `step` — the operation opens once, below,
        # after the arguments are known to be what they claim.
        self.debug(
            msg=Event.Transform,
            processor=processor,
            facade=facade,
        )
        try:
            # Explicit checks, not `assert`: assertions are removed under `python -O`.
            if not isinstance(processor, IProcessor):
                raise PipelineError(
                    caller=self, error="Expected IProcessor. Found %s" % type(processor)
                )
            if not isinstance(facade, ITarget):
                raise PipelineError(
                    caller=self, error="Expected ITarget. Found %s" % type(facade)
                )

            # Reported on ENTRY, so the audit stream reads top-down in the order
            # the activity diagram draws: pipeline -> blackboard -> repository ->
            # strategy -> driver. DEBUG, not INFO: processing a document is the
            # processor's unit of work, so the one INFO record that stands for a
            # document belongs to GenericProcessor.start — a pipeline is a step
            # inside that unit, and reporting it at INFO multiplies the stream by
            # the number of pipelines the processor drives.
            self.debug(
                msg=Event.Transform,
                step=Event.Started,
                source=NameHelper.source_name(facade),
                document=getattr(facade, "identifier", None),
            )

            result = self.transform(processor, facade, **kwargs)

            self.debug(
                msg=Event.Transform,
                step=Event.Completed,
                result=result,
            )
        except PipelineError as e:
            # The input check above: already the right exception; this layer leaves the trace.
            self.debug(msg=Event.Transform, step=Event.Failed, error=str(e))
            raise
        except Exception as e:
            # The caller stops the propagation and owns the ERROR; this layer leaves the trace and
            # carries the cause (and with it the traceback) in the exception.
            error = "%s.process error: %s" % (self.__class__.__name__, str(e))
            self.debug(msg=Event.Transform, step=Event.Failed, error=error)
            raise PipelineError(caller=self, error=error) from e


# --------------------------------------------------------------------------- #
# endregion Pipelines                                                         #
# --------------------------------------------------------------------------- #


__all__ = ["GenericPipeline", "PipelineError"]
