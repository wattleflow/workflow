# Module name: pipelines/entity/anchoring.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""The linking pipeline: hands the source to the identity driver in one call
and applies the result (SyRS-PPL-entity-anchoring)."""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = ["PipelineEntityLink"]

from wattleflow.core import IProcessor, ITarget
from wattleflow.concrete.exception import DriverException
from wattleflow.concrete.pipeline import PipelineError
from wattleflow.enums.event import Event
from wattleflow.pipelines.entity.base import GenericEntityPipeline

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Pipeline                                                             #
# --------------------------------------------------------------------------- #


class PipelineEntityLink(GenericEntityPipeline):
    """`create` asks for `write`, otherwise `read`; `apply` takes over the
    returned content. Returns the number of identities, never their words."""

    ALLOWED = ["kinds", "create", "apply", "namespace"]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        namespace = self.namespace
        if not isinstance(namespace, str) or not namespace.strip():
            raise PipelineError(caller=self, error="setting 'namespace' is required")

    def transform(self, processor: IProcessor, facade: ITarget, **kwargs) -> int | None:
        driver = self.driver_of(processor)
        source = self.source_of(facade)
        if source is None:
            self.debug(msg=Event.Transform, step=Event.Check, reason="no source")
            return None
        try:
            if self.create is True:
                result = driver.write(self.namespace, source, kinds=self.kinds)
            else:
                result = driver.read(self.namespace, source=source, kinds=self.kinds)
        except DriverException as e:
            self.debug(msg=Event.Transform, step=Event.Failed, error=type(e).__name__)
            raise PipelineError(caller=self, error=f"driver failed: {type(e).__name__}") from e
        results = result if isinstance(result, list) else [result]
        if self.apply is not False:
            content = [r.content for r in results] if isinstance(result, list) else result.content
            facade.request().update_content(content)
        return sum(len(r.identities) for r in results)


# --------------------------------------------------------------------------- #
# endregion Pipeline                                                          #
# --------------------------------------------------------------------------- #
