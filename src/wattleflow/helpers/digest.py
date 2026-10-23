# Module name: helpers/digest.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations

__all__ = ["FileDigest"]

import hashlib
import hmac
from collections.abc import Iterable
from pathlib import Path
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

Source = str | Path | bytes | bytearray | memoryview

# --------------------------------------------------------------------------- #
# region FileDigest                                                           #
# --------------------------------------------------------------------------- #


class FileDigest:
    """Content digest of a file (or raw bytes / a binary stream)."""

    DEFAULT_ALGORITHM = "sha256"
    CHUNK_SIZE = 1 << 20

    @classmethod
    def of(cls, source: Source, *, algorithm: str = DEFAULT_ALGORITHM) -> str:
        digest = hashlib.new(algorithm)
        if isinstance(source, (bytes, bytearray, memoryview)):
            digest.update(source)
        elif hasattr(source, "read"):
            while True:
                chunk = source.read(cls.CHUNK_SIZE)  # type: ignore[attr-defined]
                if not chunk:
                    break
                digest.update(chunk)
        else:
            with open(Path(source), "rb") as handle:
                for chunk in iter(lambda: handle.read(cls.CHUNK_SIZE), b""):
                    digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def labelled(cls, source: Source, *, algorithm: str = DEFAULT_ALGORITHM) -> str:
        return f"{algorithm}:{cls.of(source, algorithm=algorithm)}"

    @classmethod
    def folded(cls, digests: Iterable[str], *, algorithm: str = DEFAULT_ALGORITHM) -> str:
        """Digest OVER component digests — a compound whose parts are already
        fingerprinted (a message and its attachments, an archive and its
        entries).

        Each component is LENGTH-PREFIXED, so `("ab", "c")` and `("a", "bc")`
        cannot collide and an empty component still leaves a trace. A separator
        alone would do for fixed-width hex digests, but nothing stops a caller
        passing a labelled digest beside a bare one, or a field of its own.
        Order is the CALLER's: it carries meaning the fold cannot recover, so
        this never sorts.
        """
        folded = hashlib.new(algorithm)
        for part in digests:
            data = str(part).encode("utf-8", "surrogateescape")
            folded.update(len(data).to_bytes(8, "big"))
            folded.update(data)
        return f"{algorithm}:{folded.hexdigest()}"

    @classmethod
    def verify(cls, source: Source, expected: str, *, algorithm: str | None = None) -> bool:
        """Compare ``source`` content against ``expected`` (constant-time).

        ``expected`` may be a bare hex digest or an ``algo:hex`` label; when
        labelled, the embedded algorithm wins and ``algorithm`` is ignored.
        """
        if ":" in expected:
            algorithm, expected = expected.split(":", 1)
        actual = cls.of(source, algorithm=algorithm or cls.DEFAULT_ALGORITHM)
        return hmac.compare_digest(actual, expected)


# --------------------------------------------------------------------------- #
# endregion FileDigest                                                        #
# --------------------------------------------------------------------------- #
