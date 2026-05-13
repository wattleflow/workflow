# Module name: image_guard.py
# Author: (wattleflow@outlook.com)
# Copyright: 2022-2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""
Defensive image loader. Mitigates known image-based attacks against the
Pillow + Tesseract pipelines used by the redaction workflows:

    - decompression bombs (small file, huge pixmap),
    - format spoofing / polyglots (.png that is actually GIF, BMP, SVG, ...),
    - truncated or malformed streams,
    - oversized inputs aimed at OCR / Tika DoS,
    - path traversal when an upstream caller controls source_path.
"""

# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image, ImageFile
except Exception as e:
    raise ModuleNotFoundError(
        f"Pillow package is required to run this code.[{str(e)}\n"
        "Please install it with `pip install Pillow`"
    ) from e

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Constants                                                            #
# --------------------------------------------------------------------------- #

SAFE_MAX_PIXELS: int = 64 * 1024 * 1024
SAFE_MAX_BYTES: int = 50 * 1024 * 1024

_MAGIC: dict[str, Tuple[bytes, ...]] = {
    "PNG": (b"\x89PNG\r\n\x1a\n",),
    "JPEG": (b"\xff\xd8\xff",),
}

# Refuse truncated decoders globally; tighten Pillow's pixel cap.
ImageFile.LOAD_TRUNCATED_IMAGES = False
Image.MAX_IMAGE_PIXELS = SAFE_MAX_PIXELS

# --------------------------------------------------------------------------- #
# endregion Constants                                                         #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class ImageSecurityError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# region Global methods                                                       #
# --------------------------------------------------------------------------- #


def _within(path: Path, base: Optional[Path]) -> bool:
    if base is None:
        return True
    try:
        return path.is_relative_to(base.resolve())
    except (ValueError, OSError):
        return False


def safe_open(
    path: str | Path,
    expected: Tuple[str, ...] = ("PNG",),
    max_bytes: int = SAFE_MAX_BYTES,
    base_dir: Optional[str | Path] = None,
) -> Image.Image:
    """Return a Pillow Image only after the file passes every check.

    Pass base_dir to confine the resolved path to a trusted directory; useful
    when source_path comes through a strategy / facade boundary.
    """
    p = Path(path).resolve(strict=True)

    if base_dir is not None and not _within(p, Path(base_dir)):
        raise ImageSecurityError(f"path outside base_dir: {p}")

    size = p.stat().st_size
    if size > max_bytes:
        raise ImageSecurityError(f"image too large: {size} > {max_bytes}")
    if size == 0:
        raise ImageSecurityError(f"empty file: {p}")

    with p.open("rb") as fh:
        head = fh.read(16)
    if not any(head.startswith(m) for fmt in expected for m in _MAGIC.get(fmt, ())):
        raise ImageSecurityError(f"magic-byte mismatch for {p.name}")

    # verify() consumes the stream, so probe once then reopen for real use.
    with Image.open(p) as probe:
        probe.verify()
        if probe.format not in expected:
            raise ImageSecurityError(f"format {probe.format} not in {expected}")

    image = Image.open(p)
    image.load()
    return image


def safe_open_bytes(
    data: bytes,
    expected: Tuple[str, ...] = ("PNG",),
    max_bytes: int = SAFE_MAX_BYTES,
) -> Image.Image:
    """Same guarantees as safe_open() but for in-memory payloads."""
    import io as _io

    if not data:
        raise ImageSecurityError("empty payload")
    if len(data) > max_bytes:
        raise ImageSecurityError(f"image too large: {len(data)} > {max_bytes}")
    if not any(data.startswith(m) for fmt in expected for m in _MAGIC.get(fmt, ())):
        raise ImageSecurityError("magic-byte mismatch")

    with Image.open(_io.BytesIO(data)) as probe:
        probe.verify()
        if probe.format not in expected:
            raise ImageSecurityError(f"format {probe.format} not in {expected}")

    image = Image.open(_io.BytesIO(data))
    image.load()
    return image


# --------------------------------------------------------------------------- #
# endregion Global methods                                                    #
# --------------------------------------------------------------------------- #
