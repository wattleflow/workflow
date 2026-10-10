# Module name: concrete/serialisation.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = [
    "ConverterError",
    "FormatterError",
    "ParserError",
    "StrategyError",
    "GenericParser",
    "GenericFormatter",
    "ConversionStrategy",
    "GenericConverter",
]

from abc import ABC, abstractmethod
from contextlib import contextmanager
import os
from io import BytesIO
from typing import Any, BinaryIO, ClassVar, Union, TextIO
from pathlib import Path
from collections.abc import Iterator
from wattleflow.core import (
    IFormatter,
    IParser,
    IStrategy,
    IStrategyContext,
    IWattleflow,
)
from wattleflow.core.transactional import Content

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"


Source = Union[str, Path, bytes, bytearray, BinaryIO]
Output = Union[str, Path, TextIO, BinaryIO]

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class StrategyError(Exception):
    """A source a strategy cannot resolve."""

    def __init__(self, caller: object | None = None, error: str = "", *args):
        super().__init__(error, *args)
        self.caller = caller
        self.error = error


class ParserError(Exception):
    """A source a light parser cannot resolve or parse."""

    def __init__(self, caller: object | None = None, error: str = "", *args):
        super().__init__(error, *args)
        self.caller = caller
        self.error = error


class FormatterError(Exception):
    """Content a light formatter cannot render."""

    def __init__(self, caller: object | None = None, error: str = "", *args):
        super().__init__(error, *args)
        self.caller = caller
        self.error = error


class ConverterError(Exception):
    """A conversion that has no strategy, the wrong one, or fails in it."""

    def __init__(self, caller: object | None = None, error: str = "", *args):
        super().__init__(error, *args)
        self.caller = caller
        self.error = error


# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Classes                                                              #
# --------------------------------------------------------------------------- #


class GenericParser(IParser[Content], ABC):
    """GenericParser - light base for the read side of a format boundary."""

    ENCODING: ClassVar[str] = "utf-8"
    SOURCES: ClassVar[tuple[str, ...]] = ("stream", "path", "payload")
    ERROR: ClassVar[type[Exception]] = ParserError
    ERRORS: ClassVar[tuple[type[BaseException], ...]] = (ParserError,)

    __slots__ = ()

    @property
    def name(self) -> str:
        return type(self).__name__

    @abstractmethod
    def deserialise(self, reader: BinaryIO, **kwargs) -> Content: ...

    def parse(self, **kwargs) -> Content:
        try:
            with self._reader(kwargs) as stream:
                return self.deserialise(stream, **kwargs)
        except self.ERRORS:
            raise
        except Exception as e:
            error = "%s.parse error: %s" % (self.name, str(e))
            raise self.ERROR(caller=self, error=error) from e

    @contextmanager
    def _reader(self, kwargs: dict) -> Iterator[BinaryIO]:
        """Resolve the declared source into a binary reader."""
        declared = [key for key in self.SOURCES if key in kwargs]
        if len(declared) != 1:
            raise self.ERROR(
                caller=self,
                error=f"exactly one of {self.SOURCES} required, found {declared or 'none'}",
            )

        source = declared[0]
        value = kwargs.pop(source)
        self._check_source(source, value)

        if source == "stream":
            yield value
        elif source == "payload":
            with BytesIO(value) as buffer:
                yield buffer
        else:
            with open(value, "rb") as handle:
                yield handle

    def _check_source(self, source: str, value: object) -> None:
        if source == "stream":
            ok = callable(getattr(value, "read", None))
        elif source == "payload":
            ok = isinstance(value, (bytes, bytearray, memoryview))
        else:
            ok = isinstance(value, (str, os.PathLike))
        if not ok:
            raise self.ERROR(
                caller=self,
                error=f"{source}= is not a usable source: {type(value).__name__}",
            )

    def _decode(self, reader: BinaryIO, **kwargs) -> str:
        encoding = kwargs.pop("encoding", None) or self.ENCODING
        return reader.read().decode(encoding)


class GenericFormatter(IFormatter[Content], ABC):
    """GenericFormatter - light base for the write side of a format boundary."""

    CONTENT: ClassVar[type | None] = None
    ENCODING: ClassVar[str] = "utf-8"
    SUFFIX: ClassVar[str] = ""
    ERROR: ClassVar[type[Exception]] = FormatterError
    ERRORS: ClassVar[tuple[type[BaseException], ...]] = (FormatterError,)

    __slots__ = ()

    @property
    def name(self) -> str:
        return type(self).__name__

    @abstractmethod
    def serialise(self, content: Content, **kwargs) -> bytes | str: ...

    def render(self, **kwargs) -> bytes | str:
        if "content" not in kwargs:
            raise self.ERROR(caller=self, error="mandatory 'content' not found in kwargs")

        content = kwargs.pop("content")
        try:
            if self.CONTENT is not None:
                self.check(content)
            payload = self.serialise(content, **kwargs)
            if not isinstance(payload, (bytes, bytearray, memoryview, str)):
                raise self.ERROR(
                    caller=self,
                    error=f"serialise must return bytes or str, found {type(payload).__name__}",
                )
            return payload
        except self.ERRORS:
            raise
        except Exception as e:
            error = "%s.render error: %s" % (self.name, str(e))
            raise self.ERROR(caller=self, error=error) from e

    def _check(self, content: Content) -> None:
        """The content gate: `content` must be an instance of CONTENT."""
        if not isinstance(content, self.CONTENT):
            raise self.ERROR(
                caller=self,
                error=(
                    f"{self.name!r}: Unexpected type: Found {type(content).__name__!r} "
                    f"instead of {self.CONTENT.__name__!r}."
                ),
            )

    def _stream(self, handle: BinaryIO, content: Content, **kwargs) -> None:
        encoding = self.encoding_of(**kwargs)
        payload = self.render(content=content, **kwargs)
        try:
            handle.write(payload.encode(encoding) if isinstance(payload, str) else bytes(payload))
        except self.ERRORS:
            raise
        except Exception as e:
            error = "%s.stream error: %s" % (self.name, str(e))
            raise self.ERROR(caller=self, error=error) from e

    def _encoding_of(self, **kwargs) -> str:
        return kwargs.get("encoding") or self.ENCODING


class ConversionStrategy(IStrategy, ABC):
    """Strategy facet: convert a source into a payload of another format."""

    __slots__ = ()

    @property
    def name(self) -> str:
        return type(self).__name__

    def convert(self, caller: IWattleflow, source: Any, **kwargs) -> str | bytes:
        return self.execute(caller=caller, source=source, **kwargs)

    @abstractmethod
    def execute(self, caller: IWattleflow, **kwargs) -> str | bytes: ...


class GenericConverter(IStrategyContext, ABC):
    """GenericConverter - light context of a conversion strategy."""

    STRATEGY: ClassVar[type[IStrategy]] = IStrategy
    ERROR: ClassVar[type[Exception]] = ConverterError
    ERRORS: ClassVar[tuple[type[BaseException], ...]] = (ConverterError,)

    __slots__ = "_strategy"

    def __init__(self, strategy: IStrategy | None = None):
        super().__init__()
        self._strategy: IStrategy | None = None
        if strategy is not None:
            self.set_strategy(strategy)

    @property
    def name(self) -> str:
        return type(self).__name__

    def set_strategy(self, strategy: IStrategy) -> None:
        if not isinstance(strategy, self.STRATEGY):
            raise self.ERROR(
                caller=self,
                error=f"{strategy!r} is not a {self.STRATEGY.__name__}",
            )
        self._strategy = strategy

    def execute_strategy(self, caller: "GenericConverter", **kwargs) -> Any:
        if self._strategy is None:
            raise self.ERROR(caller=self, error="no conversion strategy set")
        try:
            return self._strategy.execute(caller, **kwargs)
        except self.ERRORS:
            raise
        except Exception as e:
            error = "%s.convert error: %s" % (self.name, str(e))
            raise self.ERROR(caller=self, error=error) from e

    def convert(self, source: Any, **kwargs) -> Any:
        return self.execute_strategy(self, source=source, **kwargs)


# --------------------------------------------------------------------------- #
# endregion Serialisation Classes                                             #
# --------------------------------------------------------------------------- #
