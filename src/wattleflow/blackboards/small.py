# Module name: blackboards/small.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

# v0.0.1.57: moved from blackwattle; it needs only the standard library.
__all__ = ["SmallBlackboard"]

from typing import Optional
from wattleflow.core import (
    IBlackboard,
    IPipeline,
    IProcessor,
    IRepository,
    ITarget,
    IWattleflow,
)
from wattleflow.concrete.blackboard import (
    TRANSITIONS,
    BlackboardAction,
    BlackboardState,
    GenericBlackboard,
)
from wattleflow.concrete.exception import BlackboardException
from wattleflow.concrete.state_machine import StateMachine
from wattleflow.enums.event import Event
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Blackboard                                                           #
# --------------------------------------------------------------------------- #


class SmallBlackboard(GenericBlackboard[ITarget]):
    __slots__ = ("_fsm",)
    ALLOWED = ["configuration", "defer_flush", "strategy_create"]

    # region Private

    def __init__(self, **kwargs):
        super().__init__(canvas=None, **kwargs)
        self._fsm: StateMachine = StateMachine(
            TRANSITIONS,
            BlackboardState.IDLE,
            name="SmallBlackboard",
        )
        self.debug(msg=Event.Constructor, step=Event.Completed)

    def __repr__(self) -> str:
        state = self._fsm.state.name or "UNKNOWN"
        return "%s:%s" % (super().__repr__(), state)

    # endregion Private

    # region Property

    @property
    def count(self) -> int:
        return 1 if self._canvas else 0

    # endregion Properties

    # region Public

    def clear(self):
        self.debug(
            msg=Event.Clear,
            step=Event.Started,
            state=self._fsm.state.name,
        )

        try:
            if self._canvas is not None and self._fsm.can(BlackboardAction.FLUSH):
                self.warning(
                    msg=Event.Clear,
                    reason="canvas has unflushed facade at lifecycle end",
                    cause="defer_flush=%s" % self.defer_flush,
                    state=self._fsm.state.name,
                )
                self.flush(caller=self)

            if isinstance(self._canvas, ITarget):
                self._canvas.clear()

            self._repositories.clear()

            if self._fsm.can(BlackboardAction.CLEAR):
                self._fsm.apply(BlackboardAction.CLEAR)
        except Exception as e:
            self.debug(
                msg=Event.Clear,
                step=Event.Failed,
                error=type(e).__name__,
            )
            if self._fsm.can(BlackboardAction.FAIL):
                self._fsm.apply(BlackboardAction.FAIL)
            raise

        self.debug(
            msg=Event.Clear,
            step=Event.Completed,
            state=self._fsm.state.name,
            repositories=len(self._repositories),
        )

    def create(self, caller: IProcessor, **kwargs) -> Optional[ITarget]:
        self.debug(msg=Event.Create, step=Event.Started, kwargs=kwargs)
        assert isinstance(caller, IProcessor), "Expected IProcessor. Found %s" % type(caller)

        if not self._strategy_create:
            self.warning(
                msg=Event.Create,
                error=f"{self.name}._strategy_create is missing!",
            )
            return None

        self.debug(msg=Event.Create, step=Event.Completed)

        return self._strategy_create.create(
            caller=self, processor=caller, blackboard=self, **kwargs
        )

    def delete(self, identifier: str, **kwargs) -> None:
        self.debug(msg=Event.Delete, step=Event.Started, id=identifier)
        if isinstance(self._canvas, ITarget):
            self.clear()
        self.debug(msg=Event.Delete, step=Event.Completed)
    def flush(self, caller: IWattleflow, **kwargs) -> bool:
        """True only when a document was on the canvas and every repository confirmed it."""
        confirmed = False
        pending = self.count
        self.debug(
            msg=Event.Flush,
            step=Event.Started,
            caller=caller,
            kwargs=kwargs,
        )

        assert isinstance(caller, (IProcessor, IBlackboard)), (
            "Expected IProcessor or IBlackboard. Found %s" % type(caller)
        )

        facade = self._canvas
        if facade is not None and self._fsm.can(BlackboardAction.FLUSH):
            self.debug(
                msg=Event.Flush,
                documents=pending,
                repositories=len(self._repositories),
            )
            try:
                confirmed = True
                for repository in self._repositories:
                    if not repository.write(caller=self, facade=facade, **kwargs):
                        confirmed = False
            except Exception as e:
                if self._fsm.can(BlackboardAction.FAIL):
                    self._fsm.apply(BlackboardAction.FAIL)

                self.debug(
                    msg=Event.Flush,
                    step=Event.Failed,
                    error=f"Writing repository: {type(e).__name__}",
                )
                raise BlackboardException(
                    self,
                    error="repository.write",
                    exc=e,
                ) from None

            if self._fsm.can(BlackboardAction.FLUSH):
                self._fsm.apply(BlackboardAction.FLUSH)

            self._canvas = None

        self.debug(msg=Event.Flush, step=Event.Completed, confirmed=confirmed)
        return confirmed

    def register(self, repository: IRepository) -> None:
        self.debug(msg=Event.Register, step=Event.Started, repository=repository)
        assert isinstance(repository, IRepository), "Expected IRepository. Found %s" % type(
            repository
        )

        if repository in self._repositories:
            self.warning(
                msg=Event.Register,
                repository=repository,
                error="Repository already registered!",
            )
            return

        self._repositories.append(repository)

        if self._fsm.can(BlackboardAction.REGISTER):
            self._fsm.apply(BlackboardAction.REGISTER)

        self.debug(
            msg=Event.Register,
            step=Event.Completed,
            state=self._fsm.state.name,
            added=repository,
        )

    def read(self, identifier: str, **kwargs) -> ITarget:
        self.debug(msg=Event.Read, step=Event.Started, kwargs=kwargs)

        if self._canvas is None:
            raise BlackboardException(self, f"Document {identifier} not found!")

        self.debug(msg=Event.Read, step=Event.Completed, identifier=identifier)
        return self._canvas

    def write(self, pipeline: IPipeline, facade: ITarget, **kwargs) -> str:
        self.debug(
            msg=Event.Write,
            step=Event.Started,
            pipeline=pipeline,
            kwargs=kwargs,
        )

        assert isinstance(pipeline, IPipeline), "Expected IPipeline. Found %s" % type(pipeline)
        assert isinstance(facade, ITarget), "Expected ITarget. Found %s" % type(facade)

        if not self._repositories:
            error = "No repositories have been registered."
            self.exception(
                msg=Event.Write,
                step=Event.Failed,
                error=error,
            )
            raise BlackboardException(self, error=error)

        self._canvas = facade

        if self._fsm.can(BlackboardAction.WRITE):
            self._fsm.apply(BlackboardAction.WRITE)

        self.debug(
            msg=Event.Write,
            document=facade.identifier,
            repositories=len(self._repositories),
            deferred=bool(self.defer_flush),
        )

        if not self.defer_flush:
            for repository in self._repositories:
                repository.write(caller=self, facade=facade, **kwargs)
            if self._fsm.can(BlackboardAction.FLUSH):
                self._fsm.apply(BlackboardAction.FLUSH)
            self._canvas = None

        self.debug(
            msg=Event.Write,
            step=Event.Completed,
            action=Event.Stored.value,
            facade=facade,
        )

        return facade.identifier

    # endregion Public


# --------------------------------------------------------------------------- #
# endregion Blackboard                                                        #
# --------------------------------------------------------------------------- #
