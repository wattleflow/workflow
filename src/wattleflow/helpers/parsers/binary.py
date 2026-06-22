# Module name: helpers/parsers/binary.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Binary Parser subclasses — read-side deserialisers for PDF, pickle, protobuf
and PNG files. Ported out of ``DriverLocalStorage._read_*`` so parsing logic
lives here, never in the driver. Third-party dependencies are lazy-imported in
``parse``.
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

__all__ = ["PdfParser", "PickleParser", "ProtobufParser", "PngParser"]

# --------------------------------------------------------------------------- #
# region Parsers                                                              #
# --------------------------------------------------------------------------- #


class PdfParser(Parser):
    """Read a PDF file. Returns raw bytes by default; pass ``extract_text=True``
    to return concatenated text via PyMuPDF."""

    def parse(self, source: Union[str, Path], **opts: Any) -> object:
        if opts.pop("extract_text", False):
            try:
                import fitz  # PyMuPDF
            except ImportError as e:
                raise ModuleNotFoundError(
                    "PyMuPDF library is missing. Add it manually: pip install PyMuPDF"
                ) from e
            doc = fitz.open(source)
            try:
                return "\n".join(page.get_text() for page in doc)
            finally:
                doc.close()
        return Path(source).read_bytes()


class PickleParser(Parser):
    """Load a pickled object. Pickle execution is unsafe by design; the caller
    must opt in explicitly via ``allow_pickle_load=True``."""

    def parse(self, source: Union[str, Path], **opts: Any) -> Any:
        if not opts.pop("allow_pickle_load", False):
            raise PermissionError(
                "PickleParser: pass allow_pickle_load=True to load untrusted pickles"
            )
        import pickle

        with open(source, "rb") as fh:
            return pickle.load(fh)


class ProtobufParser(Parser):
    """Decode a length-delimited protobuf stream into a list of dicts."""

    def parse(self, source: Union[str, Path], **opts: Any) -> list[dict]:
        from wattleflow.helpers.protobuf import (
            decode_delimited_stream,
            resolve_message_class,
        )

        schema = opts.pop("schema", None)
        message_class = opts.pop("message_class", None)
        message_cls = message_class or resolve_message_class(schema)

        with open(source, "rb") as fh:
            raw = fh.read()
        return decode_delimited_stream(raw, message_cls)


class PngParser(Parser):
    """Read a PNG file. Returns a PIL Image by default; pass ``raw_bytes=True``
    to return the original bytes instead."""

    def parse(self, source: Union[str, Path], **opts: Any) -> object:
        from wattleflow.helpers.image_guard import safe_open

        if opts.pop("raw_bytes", False):
            return Path(source).read_bytes()
        return safe_open(source, expected=("PNG",))


# --------------------------------------------------------------------------- #
# endregion Parsers                                                           #
# --------------------------------------------------------------------------- #
