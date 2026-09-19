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
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.helpers import NameHelper
from wattleflow.enums.event import Event
from wattleflow.decorators.preset import PresetDecorator
# from wattleflow.decorators.measure import measured  # retired, DR-WFL-031 v3

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


# v0.0.1.14 (DR-WFL-031 v3): retired — measurement now observes audit records; kept for the record.
# @measured()
class GenericPipeline(Wattleflow, IPipeline, ABC):
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
        if self._preset is not None:
            try:
                del self._preset
            except Exception as e:
                reason = "%s.__del__ error: %s" % (self.__class__.__name__, str(e))
                self.error(
                    msg=Event.Delete,
                    step=Event.Failed,
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
        # v0.0.1.14 (DR-WFL-031 v3): no `step` — the operation opens once, below,
        # after the arguments are known to be what they claim.
        self.debug(
            msg=Event.Transform,
            processor=processor,
            facade=facade,
        )
        try:
            assert isinstance(processor, IProcessor), "Expected IProcessor. Found %s" % type(
                processor
            )
            assert isinstance(facade, ITarget), "Expected ITarget. Found %s" % type(facade)

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
        except AssertionError as e:
            # v0.0.1.10 (DR-WFL-018 t.2): the caller stops the propagation and owns
            # the ERROR; this layer leaves the trace and carries the cause in the
            # exception.
            self.debug(msg=Event.Transform, step=Event.Failed, error=str(e))
            # v0.0.1.14: `PipelineError` takes (caller, error); the positional form raised
            # TypeError instead, so a failed input check never surfaced as a pipeline error.
            raise PipelineError(caller=self, error=str(e)) from e
        except Exception as e:
            error = "%s.process error: %s" % (self.__class__.__name__, str(e))
            self.debug(msg=Event.Transform, step=Event.Failed, error=error)
            raise PipelineError(
                caller=self,
                error=error,
                # trace=traceback.format_exc(),
            ) from e


# --------------------------------------------------------------------------- #
# endregion Pipelines                                                         #
# --------------------------------------------------------------------------- #


__all__ = ["GenericPipeline", "PipelineError"]
