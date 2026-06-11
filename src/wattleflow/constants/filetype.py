# Module name: constants/filetypes.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module provides utilities for detecting file types from URI
extensions and raw byte content using magic signatures and content heuristics.
Supports files downloaded from the web or read from local disk.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
import io
import re
from enum import Enum, auto
from pathlib import Path
from urllib.parse import urlparse
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Constants                                                            #
# --------------------------------------------------------------------------- #
# Module-level constants — defined here to avoid Enum member pollution
# OLE2 Compound Document header shared by legacy .xls and .doc files
_OLE2_MAGIC: bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# Compiled pattern for log-line recognition (reused across calls)
_LOG_RE: re.Pattern[str] = re.compile(
    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"  # ISO-8601 timestamp
    r"|\[?(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\]?"  # log level keyword
    r"|\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}",  # US date + time
    re.IGNORECASE,
)
# Extension → FileType mapping (populated once at class definition time)
_EXT_MAP: dict[str, str] = {
    ".avro": "AVRO",
    ".csv": "CSV",
    ".doc": "DOC",
    ".docx": "DOCX",
    ".json": "JSON",
    ".jsonld": "GRAPH",
    ".log": "LOG",
    ".graph": "GRAPH",
    ".md": "MARKDOWN",
    ".markdown": "MARKDOWN",
    ".orc": "ORC",
    ".pb": "PROTOBUF",
    ".protobuf": "PROTOBUF",
    ".ttl": "GRAPH",
    ".n3": "GRAPH",
    ".nt": "GRAPH",
    ".pdf": "PDF",
    ".pkl": "PICKLE",
    ".pickle": "PICKLE",
    ".png": "PNG",
    ".txt": "TXT",
    ".xls": "XLS",
    ".xlsx": "XLS",
}
# PNG signature — first 8 bytes of every PNG file per RFC 2083.
_PNG_MAGIC: bytes = b"\x89PNG\r\n\x1a\n"
# Apache Avro Object Container File — header magic "Obj\x01"
_AVRO_MAGIC: bytes = b"Obj\x01"
# Apache ORC — "ORC" at file start (writer-emitted) and again as the very
# last 3 bytes of the postscript (mandatory per ORC v1 spec).
_ORC_MAGIC: bytes = b"ORC"
# Markdown heuristics — ATX heading, fenced code block, setext underline.
_MD_RE: re.Pattern[str] = re.compile(
    r"(?m)^(#{1,6}\s+\S"        # ATX heading: '# foo'
    r"|```[\w]*$"                # fenced code block opener
    r"|[-=]{3,}\s*$)"            # setext underline
)
# Maximum bytes read from disk during content-based detection (prevents OOM)
_DETECT_MAX_BYTES: int = 50 * 1024 * 1024  # 50 MB
# XLS stream names encoded as UTF-16LE (present in OLE2 directory sectors)
_XLS_STREAM_UTF16: tuple[bytes, ...] = (
    b"W\x00o\x00r\x00k\x00b\x00o\x00o\x00k\x00",
    b"B\x00o\x00o\x00k\x00",
)
# DOC stream name encoded as UTF-16LE
_DOC_STREAM_UTF16: bytes = (
    b"W\x00o\x00r\x00d\x00D\x00o\x00c\x00u\x00m\x00e\x00n\x00t\x00"
)
# --------------------------------------------------------------------------- #
# endregion Constants                                                         #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Helpers                                                              #
# --------------------------------------------------------------------------- #


class FileType(Enum):
    AVRO = auto()
    CSV = auto()
    DOC = auto()
    DOCX = auto()
    DATAFRAME = auto()  # not detectable from content — assigned externally by callers
    JSON = auto()
    LOG = auto()
    GRAPH = auto()
    MARKDOWN = auto()
    ORC = auto()
    PDF = auto()
    PICKLE = auto()
    PROTOBUF = auto()
    PNG = auto()
    TXT = auto()
    XLS = auto()
    UNKNOWN = auto()

    @staticmethod
    def detect(uri: str) -> "FileType":
        """Detect FileType from a URI or file-system path.

        First attempts extension lookup (zero-I/O). If the extension is
        unrecognised *and* the URI points to a local file, falls back to
        content-based detection by reading the file from disk.
        Remote URLs with unknown extensions return UNKNOWN without I/O.

        Note: PROTOBUF and DATAFRAME have no magic header and are only
        recognised by extension (``.pb`` / ``.protobuf``) or by explicit
        caller assignment, respectively.
        """
        suffix = Path(urlparse(uri).path).suffix.lower()
        name = _EXT_MAP.get(suffix)
        result = FileType[name] if name else FileType.UNKNOWN
        if result is FileType.UNKNOWN:
            path = Path(uri)
            if path.is_file():
                if path.stat().st_size > _DETECT_MAX_BYTES:
                    return FileType.UNKNOWN
                result = FileType.detect_content(path.read_bytes())
        return result

    @staticmethod
    def detect_content(data: bytes) -> "FileType":
        """Detect FileType from raw bytes using magic signatures and heuristics.

        Detection order:
          1. PDF      — %PDF magic header
          2. PNG      — \\x89PNG\\r\\n\\x1a\\n magic
          3. AVRO     — Obj\\x01 magic
          4. ORC      — "ORC" at file start, or postscript tail
          5. OLE2     — legacy .xls / .doc (D0 CF 11 E0 …)
          6. OOXML    — ZIP-based .xlsx / .docx (PK\\x03\\x04)
          7. PICKLE   — protocol 2-5 magic (\\x80\\x02 … \\x80\\x05)
          8. GRAPH    — JSON-LD (@context), Turtle (@prefix/@base), N-Triples
          9. JSON     — UTF-8 starting with { or [
         10. MARKDOWN — heading / fenced code / setext heuristics
         11. LOG      — lines with timestamps / log-level keywords
         12. CSV      — consistent comma / semicolon / tab columns
         13. TXT      — any valid UTF-8 text
         14. UNKNOWN  — binary or unrecognised
        """
        if not data:
            return FileType.UNKNOWN

        # --- Binary magic checks (fast, fixed-cost) ---

        if data[:4] == b"%PDF":
            return FileType.PDF

        if data[:8] == _PNG_MAGIC:
            return FileType.PNG

        if data[:4] == _AVRO_MAGIC:
            return FileType.AVRO

        # ORC: writer emits "ORC" at file start; the postscript also ends
        # with the magic. Checking both covers truncated reads of the head
        # and full reads where only the tail is canonical.
        if data[:3] == _ORC_MAGIC or data[-3:] == _ORC_MAGIC:
            return FileType.ORC

        if data[:8] == _OLE2_MAGIC:
            return FileType._detect_ole2(data)

        if data[:4] == b"PK\x03\x04":
            return FileType._detect_zip(data)

        # Pickle protocols 2–5: \x80 followed by protocol byte (0x02–0x05)
        if data[0:1] == b"\x80" and data[1:2] in (b"\x02", b"\x03", b"\x04", b"\x05"):
            return FileType.PICKLE

        # --- Text-based heuristics ---
        return FileType._detect_text(data)

    @staticmethod
    def _detect_ole2(data: bytes) -> "FileType":
        """Distinguish XLS from DOC within an OLE2 Compound Document.

        OLE2 root directory entries begin at sector 0 (file offset 512).
        Each entry stores its name as UTF-16LE (max 32 UTF-16 code units).
        Scanning the first 4 KiB covers the root and first-level child
        directory entries in the vast majority of real-world files.
        """
        header = data[:4096]
        if any(marker in header for marker in _XLS_STREAM_UTF16):
            return FileType.XLS
        if _DOC_STREAM_UTF16 in header:
            return FileType.DOC
        # Fallback — XLS is the most common OLE2 type in data pipelines
        return FileType.XLS

    @staticmethod
    def _detect_zip(data: bytes) -> "FileType":
        """Identify OOXML sub-type (.xlsx / .docx) from ZIP central directory.
        Uses infolist() iteration with early exit so that ZIP archives with
        a large number of entries (potential zip-list exhaustion) are handled
        safely without loading the full name list into memory.
        """
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for info in zf.infolist():
                    if info.filename.startswith("xl/"):
                        return FileType.XLS
                    if info.filename.startswith("word/"):
                        return FileType.DOCX
        except Exception:  # BadZipFile, EOFError, ValueError, etc.
            pass
        return FileType.UNKNOWN

    @staticmethod
    def _detect_text(data: bytes) -> "FileType":
        """Detect text-based types: GRAPH, JSON, LOG, CSV, TXT.

        Reads at most 8 KiB to keep detection fast for large files.
        Binary data that cannot be decoded as strict UTF-8 returns UNKNOWN.
        """
        try:
            # utf-8-sig strips the UTF-8 BOM (\xef\xbb\xbf) when present,
            # preventing it from corrupting stripped[0] checks below.
            text: str = data[:8192].decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError:
            return FileType.UNKNOWN

        stripped: str = text.lstrip()
        if not stripped:
            return FileType.UNKNOWN

        # --- JSON / JSON-LD ---
        if stripped[0] in ("{", "["):
            # JSON-LD: top-level object contains "@context" key.
            # Search the raw bytes for speed — avoids full JSON parse.
            if b'"@context"' in data[:1024]:
                return FileType.GRAPH
            return FileType.JSON

        # --- RDF Turtle / N3 / N-Triples ---
        prefix = stripped[:256].lower()
        if prefix.startswith(("@prefix", "@base")):
            return FileType.GRAPH
        # N-Triples lines: <subject> <predicate> <object|literal> .
        if (
            stripped[0] == "<"
            and stripped.count("<") >= 2
            and stripped[: stripped.find("\n", 0, 512) + 1 or 512]
            .rstrip()
            .endswith(".")
        ):
            return FileType.GRAPH

        lines: list[str] = [ln for ln in stripped.splitlines() if ln.strip()]

        # --- MARKDOWN ---
        # Checked before LOG so that headings (# ...) and fenced code blocks
        # are not mis-classified as log lines.
        if _MD_RE.search(text):
            return FileType.MARKDOWN

        # --- LOG ---
        if _is_log(lines):
            return FileType.LOG

        # --- CSV / TSV ---
        if len(lines) >= 2:
            ft = _detect_delimited(lines)
            if ft is not None:
                return ft

        return FileType.TXT


def _is_log(lines: list[str]) -> bool:
    """Return True if *lines* resemble structured log output.

    At least half of the sampled lines (min 2) must match a timestamp or
    log-level pattern to avoid false positives on regular prose text.
    """
    sample = lines[:20]
    if len(sample) < 2:
        return False
    hits = sum(1 for ln in sample if _LOG_RE.search(ln))
    return hits >= max(2, len(sample) // 2)


def _detect_delimited(lines: list[str]) -> FileType | None:
    """Return FileType.CSV if content uses a consistent delimiter, else None.

    Checks comma, semicolon, and tab in that order. A format is considered
    consistent when all sampled rows share the same delimiter count (allowing
    one count difference to tolerate a trailing delimiter or quoted fields).
    """
    for delimiter in (",", ";", "\t"):
        counts = [ln.count(delimiter) for ln in lines[:10]]
        if counts[0] > 0 and len(set(counts)) <= 2:
            return FileType.CSV
    return None


# --------------------------------------------------------------------------- #
# endregion Helpers                                                           #
# --------------------------------------------------------------------------- #
