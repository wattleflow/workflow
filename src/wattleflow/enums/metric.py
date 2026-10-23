# Module name: enums/metric.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["Measure", "MetricKind", "MetricTarget"]

from enum import Enum, StrEnum
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


class MetricKind(str, Enum):
    """How a series behaves, in Prometheus' own terms."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class Measure(str, Enum):
    """A quantity an audit record may state, with its unit and its series."""

    Bytes = ("bytes", "bytes", "wf_bytes_total")
    Size = ("size", "bytes", "wf_bytes_total")
    Documents = ("documents", "documents", "wf_documents_total")
    Cycles = ("cycles", "cycles", "wf_cycles_total")
    Characters = ("chars", "characters", "wf_characters_total")
    Pages = ("pages", "pages", "wf_pages_total")
    Records = ("records", "records", "wf_records_total")
    Rows = ("rows", "rows", "wf_records_total")
    Files = ("files", "files", "wf_files_total")

    def __new__(cls, field: str, unit: str, series: str):
        member = str.__new__(cls, field)
        member._value_ = field
        member.unit = unit
        member.series = series
        return member

    @classmethod
    def fields(cls) -> tuple[str, ...]:
        """Every field name a closing record may use to state a quantity."""
        return tuple(member.value for member in cls)

    @classmethod
    def by_field(cls) -> "dict[str, Measure]":
        """Field name -> member, for a caller that looks up many keys (no normalisation)."""
        return _LOOKUP

    @classmethod
    def resolve(cls, field: str) -> "Measure | None":
        """The member for a record's field name, or None when it states none."""
        return _LOOKUP.get(str(field or "").strip().lower())


_LOOKUP: dict[str, Measure] = {member.value.lower(): member for member in Measure}


class MetricTarget(StrEnum):
    """What a record of the measurement subsystem is about (`NFRQ-ORG-12`)."""

    Export = ("export", True)
    Hotspot = ("hotspot", True)
    Limit = ("limit", True)
    Measure = ("measure", True)
    Operation = ("operation", False)
    Pair = ("pair", False)
    Resource = ("resource", True)
    Role = ("role", False)
    Run = ("run", True)
    Threshold = ("threshold", False)
    Volume = ("volume", False)

    def __new__(cls, value: str, measurement: bool):
        member = str.__new__(cls, value)
        member._value_ = value
        member.measurement = measurement
        return member

    @classmethod
    def measurements(cls) -> frozenset[str]:
        """Values of the members that carry a measured result."""
        return frozenset(member.value for member in cls if member.measurement)
