# Module name: helpers/parsers/text.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Text-family parsers — deserialise plain-text, log, Markdown, JSON and RDF
graph files into domain objects. Ported from ``DriverLocalStorage._read_*``;
parsers only deserialise (no path-security, no I/O policy, no logging).
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from pathlib import Path
from typing import Any, Union
from wattleflow.helpers.parsers.base import Parser
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = [
    "TxtParser",
    "LogParser",
    "MarkdownParser",
    "JsonParser",
    "GraphParser",
]

# --------------------------------------------------------------------------- #
# region Parsers                                                              #
# --------------------------------------------------------------------------- #


class TxtParser(Parser):
    def parse(self, source: Union[str, Path], **opts: Any) -> str:
        return Path(source).read_text(encoding=opts.pop("encoding", "utf-8"))


class LogParser(Parser):
    def parse(self, source: Union[str, Path], **opts: Any) -> str:
        return Path(source).read_text(encoding=opts.pop("encoding", "utf-8"))


class MarkdownParser(Parser):
    def parse(self, source: Union[str, Path], **opts: Any) -> str:
        return Path(source).read_text(encoding=opts.pop("encoding", "utf-8"))


class JsonParser(Parser):
    """Return the raw JSON text. Parsing is a strategy concern."""

    def parse(self, source: Union[str, Path], **opts: Any) -> str:
        return Path(source).read_text(encoding=opts.pop("encoding", "utf-8"))


class GraphParser(Parser):
    def parse(self, source: Union[str, Path], **opts: Any) -> Any:
        from rdflib import Graph

        fmt = opts.pop("format", None)
        g = Graph()
        g.parse(source, format=fmt) if fmt else g.parse(source)
        return g


# --------------------------------------------------------------------------- #
# endregion Parsers                                                           #
# --------------------------------------------------------------------------- #
