# Module name: helpers/formatters/base.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Formatter contract — serialise document content into a file payload.

A write strategy selects a Formatter (via FormatterFactory) and either:
    - calls ``render(content, **opts)`` for an in-memory payload (str|bytes)
      handed to ``DriverLocalStorage.persist(...)``, or
    - calls ``stream(fh, content, **opts)`` to write large output straight into
      a handle from ``DriverLocalStorage.open_target(...)`` — no big blob in RAM.

Formatting lives here (and in helpers/converters), never in the driver: the
driver only persists the bytes/str/stream a Formatter produces.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, BinaryIO, Union
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["Formatter"]

# --------------------------------------------------------------------------- #
# region Formatter                                                            #
# --------------------------------------------------------------------------- #


class Formatter(ABC):
    """Serialise ``content`` into a concrete file format.

    Subclasses set ``SUFFIX`` (default file extension) and implement
    ``render``. Streaming-native formatters (ORC, Avro, …) additionally
    override ``stream`` to write directly to a handle instead of buffering.
    """

    SUFFIX: str = ""

    @abstractmethod
    def render(self, content: Any, **opts: Any) -> Union[bytes, str]:
        """Return the fully serialised payload (``bytes`` or ``str``)."""

    def stream(self, fh: BinaryIO, content: Any, **opts: Any) -> None:
        """Write the serialised payload to a binary handle.

        Default buffers via ``render``; override for true streaming.
        """
        data = self.render(content, **opts)
        fh.write(data.encode("utf-8") if isinstance(data, str) else bytes(data))


# --------------------------------------------------------------------------- #
# endregion Formatter                                                         #
# --------------------------------------------------------------------------- #
