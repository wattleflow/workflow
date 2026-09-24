# Module name: concrete/serialisation.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
from abc import ABC, abstractmethod
from contextlib import contextmanager
from io import BytesIO
from typing import Any, BinaryIO, ClassVar
from collections.abc import Iterator
from wattleflow.core import IFormatter, IParser, IStrategy, IStrategyContext, IWattleflow
from wattleflow.core.transactional import Content

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"

__all__ = [
    "ConverterError",
    "FormatterError",
    "GenericConverter",
    "GenericFormatter",
    "GenericParser",
    "ParserError",
]

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


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
# region Serialisation                                                        #
# --------------------------------------------------------------------------- #


class GenericParser(IParser[Content], ABC):
    """
    GenericParser - light base for the read side of a format boundary.

    `IParser.parse` fixes no transport; this base fixes one. It resolves
    exactly one declared source into a binary reader and hands it to the
    subclass; any failure that is not already one of ERRORS becomes ERROR.
    Subclasses implement `deserialise` and never open, resolve or validate a
    path — the source policy lives here, once. No audit, no logging, no
    presets.

    Source keywords (exactly one per call):
        stream=   an already-open reader; the caller keeps ownership
        path=     a filesystem path; opened and closed by this base
        payload=  bytes; wrapped in an in-memory buffer

    ENCODING is the declared default and `encoding=` on the call the
    per-call override. `__slots__` is empty so the audit tier can combine it
    with Wattleflow, whose slots are not.
    """

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
            with self.reader(kwargs) as stream:
                return self.deserialise(stream, **kwargs)
        except self.ERRORS:
            raise
        except Exception as e:
            error = "%s.parse error: %s" % (self.name, str(e))
            raise self.ERROR(caller=self, error=error) from e

    @contextmanager
    def reader(self, kwargs: dict) -> Iterator[BinaryIO]:
        """Resolve the declared source into a binary reader.

        Consumes its own keyword out of `kwargs` so `deserialise` receives only
        format options. Override to extend the policy with a further source.
        """
        declared = [key for key in self.SOURCES if key in kwargs]
        if len(declared) != 1:
            raise self.ERROR(
                caller=self,
                error=f"exactly one of {self.SOURCES} required, found {declared or 'none'}",
            )

        source = declared[0]
        value = kwargs.pop(source)

        if source == "stream":
            # Borrowed: whoever opened it closes it.
            yield value
        elif source == "payload":
            with BytesIO(value) as buffer:
                yield buffer
        else:
            with open(value, "rb") as handle:
                yield handle

    def decode(self, reader: BinaryIO, **kwargs) -> str:
        """Read the source as text; the common case for text formats.

        Resolution order: per call, per class.
        """
        encoding = kwargs.pop("encoding", None) or self.ENCODING
        return reader.read().decode(encoding)


class GenericFormatter(IFormatter[Content], ABC):
    """
    GenericFormatter - light base for the write side of a format boundary.

    The mirror of GenericParser: it resolves and type-checks the mandatory
    `content` keyword and hands the value to the subclass; any failure that
    is not already one of ERRORS becomes ERROR. Subclasses implement
    `serialise`, declare SUFFIX (default file extension) and may declare
    CONTENT to have their input type enforced. `render` returns the payload
    and writes nothing — the caller owns the sink. Streaming-native formats
    (ORC, Avro, ...) override `stream` instead of buffering through `render`.
    No audit, no logging, no presets: GenericFormatterAudit adds them.
    """

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
            # CONTENT stays None for formats that legitimately take anything.
            if self.CONTENT is not None:
                self.check(content)
            return self.serialise(content, **kwargs)
        except self.ERRORS:
            raise
        except Exception as e:
            error = "%s.render error: %s" % (self.name, str(e))
            raise self.ERROR(caller=self, error=error) from e

    def check(self, content: Content) -> None:
        """The content gate: `content` must be an instance of CONTENT."""
        if not isinstance(content, self.CONTENT):
            raise self.ERROR(
                caller=self,
                error=(
                    f"{self.name!r}: Unexpected type: Found {type(content).__name__!r} "
                    f"instead of {self.CONTENT.__name__!r}."
                ),
            )

    def stream(self, handle: BinaryIO, content: Content, **kwargs) -> None:
        # Not an IFormatter member: a convenience over render(), so `content`
        # stays positional here.
        encoding = self.encoding_of(**kwargs)
        payload = self.render(content=content, **kwargs)
        handle.write(payload.encode(encoding) if isinstance(payload, str) else bytes(payload))

    def encoding_of(self, **kwargs) -> str:
        """The text encoding of a call: per call, per class."""
        return kwargs.get("encoding") or self.ENCODING


# --------------------------------------------------------------------------- #
# endregion Serialisation                                                     #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Conversion                                                           #
# --------------------------------------------------------------------------- #


class GenericConverter(IStrategyContext, ABC):
    """
    GenericConverter - light context of a conversion strategy.

    Converts a source of one format into a payload of another by running the
    strategy it holds; IParser and IFormatter are the strategy's parts, and a
    strategy of its own is justified by what happens between parse and render
    (a transform), not by the choice of formatter. Not an IDriver: no device,
    no resource lifecycle, no persistence.

    STRATEGY narrows what `set_strategy` accepts (default: any IStrategy). A
    strategy is called as `execute(caller, source=..., **options)` and returns
    the payload. A failure that is not already one of ERRORS becomes ERROR.

    `__slots__` is empty so GenericConverterAudit can combine it with
    Wattleflow; `_strategy` is a slot of the tier that holds it. A light
    subclass declares `__slots__ = ("_strategy",)` to stay dict-free once the
    core interfaces carry `__slots__ = ()`; until then the instance dict holds
    it.
    """

    STRATEGY: ClassVar[type[IStrategy]] = IStrategy
    ERROR: ClassVar[type[Exception]] = ConverterError
    ERRORS: ClassVar[tuple[type[BaseException], ...]] = (ConverterError,)

    __slots__ = ()

    def __init__(self, strategy: IStrategy | None = None):
        self._strategy: IStrategy | None = None
        if strategy is not None:
            self.set_strategy(strategy)

    @property
    def name(self) -> str:
        return type(self).__name__

    @property
    def strategy(self) -> IStrategy | None:
        return self._strategy

    def set_strategy(self, strategy: IStrategy) -> None:
        if not isinstance(strategy, self.STRATEGY):
            raise self.ERROR(
                caller=self,
                error=f"{strategy!r} is not a {self.STRATEGY.__name__}",
            )
        self._strategy = strategy

    def execute_strategy(self, caller: IWattleflow, **kwargs) -> Any:
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
        """Convert `source`; the converter is the strategy's caller."""
        return self.execute_strategy(self, source=source, **kwargs)


# --------------------------------------------------------------------------- #
# endregion Conversion                                                        #
# --------------------------------------------------------------------------- #
