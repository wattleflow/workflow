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
from wattleflow.core import IFormatter, IParser
from wattleflow.core.transactional import Content
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.helpers import Attribute
from wattleflow.concrete.base import Wattleflow
from wattleflow.enums.event import Event
from wattleflow.decorators.preset import PresetDecorator

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__author__ = "WattleFlow"
__copyright__ = "© 2022–2026 WattleFlow. All rights reserved"
__license__ = "Apache 2 Licence"

__all__ = ["FormatterError", "GenericFormatter", "GenericParser", "ParserError"]

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class ParserError(AuditException):
    pass


class FormatterError(AuditException):
    pass


# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Serialisation                                                        #
# --------------------------------------------------------------------------- #


class GenericParser(Wattleflow, IParser[Content], ABC):
    """
    GenericParser - framework base for the read side of a format boundary.

    `IParser.parse` fixes no transport; this base fixes one. It resolves
    exactly one declared source into a binary reader, audits the attempt and
    converts any failure into ParserError, then hands the reader to the
    subclass. Subclasses implement `deserialise` and never open, resolve or
    validate a path — the source policy lives here, once.

    Source keywords (exactly one per call):
        stream=   an already-open reader; the caller keeps ownership
        path=     a filesystem path; opened and closed by this base
        payload=  bytes; wrapped in an in-memory buffer

    ENCODING is the declared default, `encoding=` on the constructor the
    per-instance override (NFRQ-ORG-07) and `encoding=` on the call the
    per-call one. A subclass that declares its own ALLOWED *replaces* this one
    — PresetDecorator resolves a single class attribute, it does not merge — so
    such a subclass must repeat every key it still needs.
    """

    ALLOWED = ["encoding"]
    ENCODING: ClassVar[str] = "utf-8"
    SOURCES: ClassVar[tuple[str, ...]] = ("stream", "path", "payload")

    __slots__ = ("_preset",)

    def __init__(self, **kwargs):
        # Wattleflow is the single place that splits logging keywords off; a
        # subclass forwards its whole **kwargs unchanged and names none of them.
        super().__init__(**kwargs)
        self.debug(msg=Event.Constructor.name)
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

    # region Private
    def __getattr__(self, name: str) -> Any:
        # During partial construction _preset is absent: report the attribute
        # as missing rather than surface the internal lookup failure.
        try:
            preset: PresetDecorator | None = object.__getattribute__(self, "_preset")
        except AttributeError:
            preset = None
        if preset is None:
            raise AttributeError(name)
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}"

    # endregion

    @abstractmethod
    def deserialise(self, reader: BinaryIO, **kwargs) -> Content: ...

    def parse(self, **kwargs) -> Content:
        self.debug(msg=Event.Read.name, step=Event.Starting.name)
        try:
            with self.reader(kwargs) as stream:
                content = self.deserialise(stream, **kwargs)
        except AuditException:
            raise
        except Exception as e:
            error = "%s.parse error: %s" % (self.name, str(e))
            self.debug(msg=Event.Read.name, step=Event.Failed.name, error=error)
            raise ParserError(caller=self, error=error) from e

        self.debug(
            msg=Event.Read.name,
            step=Event.Completed.name,
            content=Attribute.type_name(content),
        )
        return content

    @contextmanager
    def reader(self, kwargs: dict) -> Iterator[BinaryIO]:
        """Resolve the declared source into a binary reader.

        Consumes its own keyword out of `kwargs` so `deserialise` receives only
        format options. Override to extend the policy with a further source.
        """
        declared = [key for key in self.SOURCES if key in kwargs]
        if len(declared) != 1:
            raise ParserError(
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

        Resolution order: per call, per instance (preset), per class.
        """
        encoding = kwargs.pop("encoding", None) or self.encoding or self.ENCODING
        return reader.read().decode(encoding)


class GenericFormatter(Wattleflow, IFormatter[Content], ABC):
    """
    GenericFormatter - framework base for the write side of a format boundary.

    The mirror of GenericParser: it resolves and type-checks the mandatory
    `content` keyword, audits the attempt and converts any failure into
    FormatterError, then hands the value to the subclass. Subclasses implement
    `serialise`, declare SUFFIX (default file extension) and may declare
    CONTENT to have their input type enforced. `render` returns the payload and
    writes nothing — the caller owns the sink. Streaming-native formats (ORC,
    Avro, ...) override `stream` instead of buffering through `render`.
    """

    ALLOWED = ["encoding"]
    CONTENT: ClassVar[type | None] = None
    ENCODING: ClassVar[str] = "utf-8"
    SUFFIX: ClassVar[str] = ""

    __slots__ = ("_preset",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.debug(msg=Event.Constructor.name)
        self._preset: PresetDecorator = PresetDecorator(self, **kwargs)

    # region Private
    def __getattr__(self, name: str) -> Any:
        try:
            preset: PresetDecorator | None = object.__getattribute__(self, "_preset")
        except AttributeError:
            preset = None
        if preset is None:
            raise AttributeError(name)
        return preset.__getattr__(name)

    def __repr__(self) -> str:
        return f"{self.name}"

    # endregion

    @abstractmethod
    def serialise(self, content: Content, **kwargs) -> bytes | str: ...

    def render(self, **kwargs) -> bytes | str:
        self.debug(msg=Event.Render.name, step=Event.Starting.name)
        if "content" not in kwargs:
            raise FormatterError(caller=self, error="mandatory 'content' not found in kwargs")

        content = kwargs.pop("content")
        try:
            # Attribute.evaluate is the house type gate; CONTENT stays None for
            # formats that legitimately take anything.
            if self.CONTENT is not None:
                Attribute.evaluate(self, content, self.CONTENT)
            payload = self.serialise(content, **kwargs)
        except AuditException:
            raise
        except Exception as e:
            error = "%s.render error: %s" % (self.name, str(e))
            self.debug(msg=Event.Render.name, step=Event.Failed.name, error=error)
            raise FormatterError(caller=self, error=error) from e

        self.debug(msg=Event.Render.name, step=Event.Completed.name, size=len(payload))
        return payload

    def stream(self, handle: BinaryIO, content: Content, **kwargs) -> None:
        # Not an IFormatter member: a convenience over render(), so `content`
        # stays positional here.
        encoding = kwargs.get("encoding") or self.encoding or self.ENCODING
        payload = self.render(content=content, **kwargs)
        handle.write(payload.encode(encoding) if isinstance(payload, str) else bytes(payload))


# --------------------------------------------------------------------------- #
# endregion Serialisation                                                     #
# --------------------------------------------------------------------------- #
