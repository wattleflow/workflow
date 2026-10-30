# Module name: pipelines/entity/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""Pipelines that ask the identity driver about entities (SyRS-PPL-entity)."""

from __future__ import annotations

__all__ = ["GenericEntityPipeline", "PipelineEntityLink"]

from wattleflow.pipelines.entity.anchoring import PipelineEntityLink
from wattleflow.pipelines.entity.base import GenericEntityPipeline
