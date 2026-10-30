# Module name: pipelines/entity/base.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""Common base of entity pipelines: the processor's identity driver and the
source handed to it (SyRS-PPL-entity)."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["GenericEntityPipeline"]

from abc import ABC
from typing import Any

from wattleflow.core import IProcessor, ITarget
from wattleflow.concrete.pipeline import GenericPipeline, PipelineError
from wattleflow.drivers.identity.driver import DriverIdentity

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Pipeline                                                             #
# --------------------------------------------------------------------------- #


class GenericEntityPipeline(GenericPipeline, ABC):
    """Gives an aspect the driver and the source; it recognises nothing itself
    (StRS BR01, BR04)."""

    ALLOWED = ["kinds"]

    def driver_of(self, processor: IProcessor) -> DriverIdentity:
        driver = getattr(processor, "driver", None)
        if not isinstance(driver, DriverIdentity):
            raise PipelineError(
                caller=self,
                error=f"processor {getattr(processor, 'name', type(processor).__name__)} has no identity driver",
            )
        return driver

    @staticmethod
    def source_of(facade: ITarget) -> Any:
        content = getattr(facade.request(), "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list) and content:
            if all(isinstance(row, dict) for row in content):
                return content
            if all(isinstance(text, str) for text in content):
                return content
        return None


# --------------------------------------------------------------------------- #
# endregion Pipeline                                                          #
# --------------------------------------------------------------------------- #
