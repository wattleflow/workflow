# Module name: filetypes.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module provides utilities for detecting file types from URI
extensions and raw byte content using magic signatures and content heuristics.
Supports files downloaded from the web or read from local disk.
"""

from __future__ import annotations

import io
from enum import Enum, auto
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


# Module-level constants — defined here to avoid Enum member pollution
# OLE2 Compound Document header shared by legacy .xls and .doc files
_OLE2_MAGIC: bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

import re

# Compiled pattern for log-line recognition (reused across calls)
_LOG_RE: re.Pattern[str] = re.compile(
    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"  # ISO-8601 timestamp
    r"|\[?(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\]?"  # log level keyword
    r"|\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}",  # US date + time
    re.IGNORECASE,
)

# Extension → FileType mapping (populated once at class definition time)
_EXT_MAP: dict[str, str] = {
    ".csv": "CSV",
    ".doc": "DOC",
    ".docx": "DOC",
    ".json": "JSON",
    ".jsonld": "GRAPH",
    ".log": "LOG",
    ".graph": "GRAPH",
    ".ttl": "GRAPH",
    ".n3": "GRAPH",
    ".nt": "GRAPH",
    ".pdf": "PDF",
    ".txt": "TXT",
    ".xls": "XLS",
    ".xlsx": "XLS",
}

# XLS stream names encoded as UTF-16LE (present in OLE2 directory sectors)
_XLS_STREAM_UTF16: tuple[bytes, ...] = (
    b"W\x00o\x00r\x00k\x00b\x00o\x00o\x00k\x00",
    b"B\x00o\x00o\x00k\x00",
)

# DOC stream name encoded as UTF-16LE
_DOC_STREAM_UTF16: bytes = (
    b"W\x00o\x00r\x00d\x00D\x00o\x00c\x00u\x00m\x00e\x00n\x00t\x00"
)


class FileType(Enum):
    CSV = auto()
    DOC = auto()
    JSON = auto()
    LOG = auto()
    GRAPH = auto()
    PDF = auto()
    TXT = auto()
    XLS = auto()
    UNKNOWN = auto()

    @staticmethod
    def detect(uri: str) -> "FileType":
        """Detect FileType from a URI or file-system path by extension.

        This is the fast, zero-I/O method used when the file path or URL
        is already known. Falls back to UNKNOWN for unrecognised extensions.
        """
        suffix = Path(urlparse(uri).path).suffix.lower()
        name = _EXT_MAP.get(suffix)
        result = FileType[name] if name else FileType.UNKNOWN
        if result is FileType.UNKNOWN:
            raw_content = Path(uri).read_bytes()
            result = FileType.detect_content(raw_content)
        return result

    @staticmethod
    def detect_content(data: bytes) -> "FileType":
        """Detect FileType from raw bytes using magic signatures and heuristics.

        Detection order:
          1. PDF      — %PDF magic header
          2. OLE2     — legacy .xls / .doc (D0 CF 11 E0 …)
          3. OOXML    — ZIP-based .xlsx / .docx (PK\\x03\\x04)
          4. GRAPH    — JSON-LD (@context), Turtle (@prefix/@base), N-Triples
          5. JSON     — UTF-8 starting with { or [
          6. LOG      — lines with timestamps / log-level keywords
          7. CSV      — consistent comma / semicolon / tab columns
          8. TXT      — any valid UTF-8 text
          9. UNKNOWN  — binary or unrecognised
        """
        if not data:
            return FileType.UNKNOWN

        # --- Binary magic checks (fast, fixed-cost) ---

        if data[:4] == b"%PDF":
            return FileType.PDF

        if data[:8] == _OLE2_MAGIC:
            return FileType._detect_ole2(data)

        if data[:4] == b"PK\x03\x04":
            return FileType._detect_zip(data)

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
                        return FileType.DOC
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
            text: str = data[:8192].decode("utf-8", errors="strict")
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


def _detect_delimited(lines: list[str]) -> Optional[FileType]:
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


if __name__ == "__main__":
    import gc

    try:
        import gc

        dd = FileType().detect(
            "src/wattleflow/api/controllers/dockers/flight-sim/image-conflict-sim/data/iran.json"
        )
        print(dd)
    except Exception as e:
        msg = f"Global exception:{e}"
        print(msg)
    finally:
        gc.collect()
