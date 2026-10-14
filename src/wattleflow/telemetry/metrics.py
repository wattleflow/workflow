# Module name: telemetry/metrics.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["MetricSample", "MetricSink"]

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Mapping, Sequence
from wattleflow.enums.metric import MetricKind
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class MetricSample:
    """One published series point."""

    name: str
    kind: MetricKind
    labels: Mapping[str, str] = field(default_factory=dict)
    value: float = 0.0
    buckets: Mapping[str, int] | None = None
    unit: str = ""


class MetricSink(ABC):
    """One destination. It formats; a driver ships."""

    @abstractmethod
    def publish(self, samples: Sequence[MetricSample]) -> bool: ...


# --------------------------------------------------------------------------- #
# endregion Classes                                                           #
# --------------------------------------------------------------------------- #
