# Module name: telemetry/filters.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["MeasurementFilter"]

from logging import Filter
from wattleflow.constants.audit import TARGET_ATTRIBUTE
from wattleflow.enums.metric import MetricTarget
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


class MeasurementFilter(Filter):
    """Pass only records that carry a measured result (`MetricTarget`)."""

    TARGETS = MetricTarget.measurements()

    def filter(self, record):
        return getattr(record, TARGET_ATTRIBUTE, None) in self.TARGETS
