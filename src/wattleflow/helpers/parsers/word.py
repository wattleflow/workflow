# Module name: helpers/parsers/word.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Word-document parsers — read-side deserialisation for DOCX and legacy DOC.

Ported out of ``DriverLocalStorage._read_docx`` / ``_read_doc`` so the parsing
logic lives here, not in the driver. Both reuse ``WordConverter`` and return
Markdown text. ``DocParser`` first converts a legacy ``.doc`` to ``.docx`` via
headless LibreOffice.
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

__all__ = ["DocxParser", "DocParser"]

# --------------------------------------------------------------------------- #
# region Parsers                                                              #
# --------------------------------------------------------------------------- #


class DocxParser(Parser):
    """Read a DOCX file and return Markdown-formatted text."""

    def parse(self, source: Union[str, Path], **opts: Any) -> str:
        from wattleflow.helpers.converters import WordConverter

        return WordConverter.read_docx(str(source))


class DocParser(Parser):
    """Read a legacy .doc file by converting it to .docx via LibreOffice,
    then extracting Markdown text via WordConverter.
    """

    def parse(self, source: Union[str, Path], **opts: Any) -> str:
        import shutil
        import subprocess
        import tempfile

        from wattleflow.helpers.converters import WordConverter

        uri = str(source)
        binary = shutil.which("libreoffice") or shutil.which("soffice")
        if binary is None:
            raise RuntimeError(
                "LibreOffice not found. Install: sudo apt install libreoffice"
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [binary, "--headless", "--convert-to", "docx", "--outdir", tmpdir, uri],
                capture_output=True,
                text=True,
                timeout=opts.pop("timeout", 120),
                check=False,
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(f"LibreOffice .doc conversion failed: {detail}")
            docx_path = next(Path(tmpdir).glob("*.docx"), None)
            if docx_path is None:
                raise RuntimeError(
                    "LibreOffice produced no .docx output for .doc input"
                )
            return WordConverter.read_docx(str(docx_path))


# --------------------------------------------------------------------------- #
# endregion Parsers                                                           #
# --------------------------------------------------------------------------- #
