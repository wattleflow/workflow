# Module name: helpers/routing.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = [
    "ROUTE_KEY",
    "RoutingLabel",
    "RoutingRule",
    "PatternSpec",
    "route_label",
    "route_target",
    "DestinationRouter",
    "LocalStorageDestinationRouter",
]

import fnmatch
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

ROUTE_KEY = "route"

# --------------------------------------------------------------------------- #
# region Classification                                                       #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RoutingLabel:
    name: str
    target: str


class RoutingRule:
    def __init__(
        self,
        fmt: str | None,
        matchers: tuple[tuple[Callable[[str], bool], RoutingLabel], ...],
        labels: tuple[RoutingLabel, ...],
    ) -> None:
        self.fmt: str | None = fmt
        self.labels: tuple[RoutingLabel, ...] = labels
        self._matchers = matchers

    @staticmethod
    def _matcher(
        name: str, glob: str | None, regex: str | None, fmt: str | None
    ) -> Callable[[str], bool]:
        if regex:
            compiled = re.compile(regex)
            return lambda candidate: compiled.search(candidate) is not None
        if glob:
            needle = glob.lower()
            return lambda candidate: fnmatch.fnmatchcase(candidate.lower(), needle)
        if fmt:
            compiled = re.compile(fmt.replace("{label}", re.escape(name)))
            return lambda candidate: compiled.search(candidate) is not None
        needle = name.lower()
        return lambda candidate: fnmatch.fnmatchcase(candidate.lower(), needle)

    @classmethod
    def build(cls, fmt: str | None, labels: Any) -> "RoutingRule":
        fmt = fmt or None
        parsed: list[RoutingLabel] = []
        matchers: list[tuple[Callable[[str], bool], RoutingLabel]] = []
        for entry in labels or []:
            glob = regex = None
            if isinstance(entry, str):
                name = target = entry
            elif isinstance(entry, Mapping):
                name = entry.get("name") or entry.get("label")
                target = (
                    entry.get("target")
                    or entry.get("directory")
                    or entry.get("dir")
                    or name
                )
                glob = entry.get("match") or entry.get("glob")
                regex = entry.get("regex")
            else:
                continue
            if not (name or target):
                continue
            name = str(name or target)
            target = str(target or name)
            label = RoutingLabel(name=name, target=target)
            parsed.append(label)
            matchers.append((cls._matcher(name, glob, regex, fmt), label))
        return cls(fmt, tuple(matchers), tuple(parsed))

    def classify(self, name: str) -> RoutingLabel | None:
        for matcher, label in self._matchers:
            if matcher(name):
                return label
        return None


@dataclass(frozen=True)
class PatternSpec:
    glob: str
    rule: RoutingRule | None = None

    @classmethod
    def parse(cls, pattern: str | Mapping[str, Any]) -> "PatternSpec":
        if isinstance(pattern, str):
            return cls(glob=pattern, rule=None)
        if isinstance(pattern, Mapping):
            glob = pattern.get("glob") or pattern.get("pattern") or "*"
            labels = pattern.get("labels")
            rule = RoutingRule.build(pattern.get("format"), labels) if labels else None
            return cls(glob=str(glob), rule=rule)
        raise TypeError(
            f"pattern must be str or mapping, got {type(pattern).__name__}"
        )


def route_label(metadata: Mapping[str, Any]) -> str | None:
    value = metadata.get(ROUTE_KEY)
    return str(value) if value else None


def route_target(metadata: Mapping[str, Any]) -> str | None:
    name = route_label(metadata)
    if not name:
        return None
    value = metadata.get(name)
    return str(value) if value else None


# --------------------------------------------------------------------------- #
# endregion Classification                                                    #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Resolution                                                           #
# --------------------------------------------------------------------------- #


class DestinationRouter(ABC):
    @abstractmethod
    def resolve(self, route: str, *, filename: str, **kwargs: Any) -> Mapping[str, Any]: ...


class LocalStorageDestinationRouter(DestinationRouter):
    def resolve(
        self,
        route: str,
        *,
        filename: str,
        suffix: str | None = None,
        extra: str | None = None,
        mkdir: bool = True,
        **_: Any,
    ) -> Mapping[str, Any]:
        subdir = f"{route}/{extra}" if extra else route
        destination: dict[str, Any] = {
            "filename": Path(filename).name,
            "subdir": subdir,
            "mkdir": mkdir,
        }
        if suffix is not None:
            destination["suffix"] = suffix
        return destination


# --------------------------------------------------------------------------- #
# endregion Resolution                                                        #
# --------------------------------------------------------------------------- #
