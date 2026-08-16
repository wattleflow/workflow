# Module name: helpers/digest.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

# --------------------------------------------------------------------------- #
# Content digest (protective hash) of a FILE — a fingerprint computed over the
# file's BYTES, never its path, so identical content yields the same digest
# regardless of name or location. Streaming (bounded memory) for large files.
# Used to fingerprint originals for evidence integrity and to verify a file (by
# CONTENT, not path) against a known digest. Stdlib-only (hashlib/hmac) → clean
# core / zero-trust safe.
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #
from __future__ import annotations
import hashlib
import hmac
from pathlib import Path
# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = ["FileDigest"]

Source = str | Path | bytes | bytearray | memoryview

# --------------------------------------------------------------------------- #
# region FileDigest                                                           #
# --------------------------------------------------------------------------- #


class FileDigest:
    """Content digest of a file (or raw bytes / a binary stream).

    ``of`` computes the hex digest; ``labelled`` prefixes the algorithm
    (``sha256:…``) so a stored digest is self-describing and portable across
    stores; ``verify`` compares content against an expected digest in constant
    time. All operate on CONTENT, so a digest is stable across copies/renames.
    """

    DEFAULT_ALGORITHM = "sha256"
    CHUNK_SIZE = 1 << 20  # 1 MiB streaming granularity

    @classmethod
    def of(cls, source: Source, *, algorithm: str = DEFAULT_ALGORITHM) -> str:
        digest = hashlib.new(algorithm)
        if isinstance(source, (bytes, bytearray, memoryview)):
            digest.update(source)
        elif hasattr(source, "read"):
            # Binary stream (already open) — consumed in chunks.
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
        # e.g. "sha256:9f86d0…" — algorithm travels with the digest.
        return f"{algorithm}:{cls.of(source, algorithm=algorithm)}"

    @classmethod
    def verify(
        cls, source: Source, expected: str, *, algorithm: str | None = None
    ) -> bool:
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
