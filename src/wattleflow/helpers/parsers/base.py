# Module name: helpers/parsers/base.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Parser contract — the read-side mirror of helpers.formatters.

A Parser turns a file on disk into a domain object (DataFrame, list[dict],
rdflib Graph, str, PIL Image, …). ``DriverLocalStorage.read`` validates and
detects the file type, then delegates to ``ParserFactory.create(ftype).parse``
— so parsing logic lives here, never in the driver. The driver only does I/O
and path-security checks.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Union
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["Parser"]

# --------------------------------------------------------------------------- #
# region Parser                                                               #
# --------------------------------------------------------------------------- #


class Parser(ABC):
    """Deserialise a file at ``source`` into a domain object.

    ``source`` is an already validated path (the driver enforces the
    base-directory sandbox before calling). Subclasses lazy-import their
    third-party dependency inside ``parse``.
    """

    @abstractmethod
    def parse(self, source: Union[str, Path], **opts: Any) -> Any:
        """Read and deserialise the file at ``source``."""


# --------------------------------------------------------------------------- #
# endregion Parser                                                            #
# --------------------------------------------------------------------------- #
