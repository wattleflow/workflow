# Module name: local_file_system_driver.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations

import fnmatch
import pandas as pd
from rdflib import Graph
from pathlib import Path
from typing import Any, Generator
from wattleflow.concrete import GenericDriver
from wattleflow.concrete.driver import DriverAction, DriverMetadata
from wattleflow.concrete.exception import AuditException
from wattleflow.constants.enums import Event
from wattleflow.constants.filetype import FileType
from wattleflow.drivers import FileStorage
from wattleflow.helpers.attribute import Attribute
from wattleflow.helpers.image_guard import safe_open, safe_open_bytes


class LocalStorageDriverException(AuditException):
    pass


class LocalStorageDriver(GenericDriver):
    __allowed__ = ["current_path", "create", "local_path", "normalised"]

    def __init__(self, **kwargs) -> None:
        kwargs.pop("allowed", None)
        GenericDriver.__init__(self, allowed=self.__allowed__, **kwargs)
        self.ensure_live()

    def close(self) -> None:
        self.debug(msg="close", step=Event.Started.name)
        if not self.can(DriverAction.UNLOAD):
            return
        self.debug(msg="close", step=Event.Completed.name)

    def metadata(self) -> DriverMetadata:
        return DriverMetadata(
            name=self.__class__.__name__,
            version="1.0",
            protocol="file",
            capabilities=["read", "write", "search"],
        )

    def load(self) -> None:
        self.debug(msg=Event.Loading.name, step=Event.Started.name)

        self.create = self.create or False
        self.normalised = self.normalised or False
        self.local_path = Path(self.local_path)
        self.current_path: Path = self.local_path

        if not self.local_path.is_dir():
            if not self.create:
                reason = f"local_path should be directory: {str(self.local_path)!r}"
                self.error(
                    msg=Event.Constructor.value,
                    reason=reason,
                    local_path=str(self.local_path),
                )
                self._fsm.apply(DriverAction.LOAD_FAIL)
                raise RuntimeError(reason)
            self.local_path.mkdir(parents=True, exist_ok=True)

        self.debug(
            msg=Event.Loading.name,
            step=Event.Completed.name,
            create=self.create,
            normalised=self.normalised,
            local_path=str(self.local_path),
        )

    def read(self, uri: str, **kwargs) -> Any:
        self.debug(msg=Event.Read.name, step=Event.Starting.name, uri=uri, **kwargs)
        _uri = Path(uri).resolve()
        _base = Path(self.local_path).resolve()

        if not _uri.is_relative_to(_base):
            reason = f"Access denied: path outside base directory: {str(uri)!r}"
            self.error(msg=Event.Read.name, uri=uri, reason=reason)
            raise PermissionError(reason)

        try:
            filetype = FileType.detect(str(_uri))
            self.debug(
                msg=Event.Read.name,
                step=Event.Completed.name,
                filetype=filetype.name,
                uri=_uri.as_uri(),
                **kwargs,
            )
            match filetype:
                case FileType.CSV:
                    return pd.read_csv(_uri, **kwargs)
                case FileType.JSON:
                    return pd.read_json(_uri, **kwargs)
                case FileType.TXT | FileType.UNKNOWN:
                    return _uri.read_text()
                case FileType.XLS:
                    return pd.read_excel(_uri, **kwargs)
        except AuditException as e:
            self.error(msg=Event.Read.name, uri=uri, error=e.reason)
            raise LocalStorageDriverException(caller=self, error=e.reason, uri=uri) from e
        except Exception as e:
            self.error(msg=Event.Read.name, uri=uri, error=str(e))
            raise LocalStorageDriverException(caller=self, error=str(e), uri=uri) from e

    def write(
        self,
        uri: str,
        filename: str,
        ftype: FileType,
        content: object,
        **kwargs,
    ) -> str:
        self.debug(
            msg=Event.Write.name,
            step=Event.Started.name,
            uri=uri,
            filename=str(filename),
            ftype=ftype.value,
            content=type(content).__name__,
            **kwargs,
        )

        mkdir = kwargs.pop("mkdir", False)
        subdir = kwargs.pop("subdir", None)

        if subdir:
            self.__change_dir(subdir, mkdir)

            # try:
        storage = FileStorage(
            local_path=str(self.current_path.resolve()),
            uri=filename,
            create=self.create,
            normalised=self.normalised,
        )
        # except Exception as e:
        #     self.error(msg=Event.Write.name, filename=str(filename), error=str(e))
        #     raise LocalStorageDriverException(
        #         caller=self, error=str(e), filename=str(filename)
        #     ) from e

        if ftype == FileType.TXT:
            return self._write_txt(storage=storage, content=content, **kwargs)
        if ftype == FileType.CSV or ftype == FileType.DATAFRAME:
            return self._write_csv(storage=storage, content=content, **kwargs)
        if ftype == FileType.JSON:
            return self._write_json(storage=storage, content=content, **kwargs)
        if ftype == FileType.GRAPH:
            return self._write_graph(storage=storage, content=content, **kwargs)
        if ftype == FileType.PNG:
            return self._write_png(storage=storage, content=content, **kwargs)
        if ftype == FileType.PDF:
            return self._write_pdf(storage=storage, content=content, **kwargs)

        self.error(
            msg=Event.Write.value,
            error=f"unknown type: {ftype}",
            filename=storage.filename,
            origin=storage.origin,
            digest=storage.digest,
            content=content,
        )
        raise TypeError("Unknown file type!")

    def search(
        self, pattern: str, case_sensitive: bool = False, recursive: bool = False
    ) -> Generator[Path, None, None]:
        self.debug(
            msg=Event.Search.name,
            step=Event.Started.name,
            pattern=pattern,
            case_sensitive=case_sensitive,
            recursive=recursive,
        )
        search_path = getattr(self, "current_path", None) or getattr(self, "local_path", None)
        if search_path is None:
            raise RuntimeError("search: local_path is not configured")
        search_path = Path(search_path).resolve()

        self.debug(
            msg=Event.Search.value,
            step=Event.Started.value,
            pattern=pattern,
            case_sensitive=case_sensitive,
            recursive=recursive,
            search_path=str(search_path),
        )

        iterator = search_path.rglob("*") if recursive else search_path.glob("*")

        for path in iterator:
            name = path.name
            if "*" in pattern or "?" in pattern or "[" in pattern:
                if case_sensitive:
                    if fnmatch.fnmatchcase(name, pattern):
                        yield path
                else:
                    if fnmatch.fnmatchcase(name.lower(), pattern.lower()):
                        yield path
            else:
                if case_sensitive:
                    if pattern in name:
                        yield path
                else:
                    if pattern.lower() in name.lower():
                        yield path

        self.debug(
            msg=Event.Search.name,
            step=Event.Completed.name,
        )

    # region private methods
    def __change_dir(self, name: str, mkdir=True) -> str:
        self.debug(
            msg=Event.Move.value,
            name=name,
            mkdir=mkdir,
        )

        _base = Path(self.local_path).resolve()
        _resolved = _base.joinpath(name).resolve()
        if not _resolved.is_relative_to(_base):
            reason = f"Path traversal detected: {name!r}"
            self.error(msg=Event.Move.value, name=name, reason=reason)
            raise PermissionError(reason)

        self.current_path = Path(_resolved)

        if mkdir:
            if self.current_path.exists() is False:
                self.current_path.mkdir(parents=True)

        self.debug(
            msg=Event.Move.value,
            step=Event.Completed.value,
            current_path=str(self.current_path),
        )
        return str(self.current_path)

    def _write_txt(self, storage: FileStorage, content: str, **kwargs) -> str:
        self.debug(
            msg=Event.Write.value,
            step=Event.Started.value,
            filename=storage.filename,
            uri=storage.uri,
            digest=storage.digest,
            **kwargs,
        )

        suffix = kwargs.pop("suffix", ".txt")
        output = storage.with_suffix(suffix)
        output.write_text(content)

        self.debug(
            msg=Event.Write.value,
            step=Event.Completed.value,
            output=output,
        )

        return output

    def _write_csv(self, storage: FileStorage, content: pd.DataFrame, **kwargs) -> str:
        self.debug(
            msg=f"{Event.Write.name}_csv",
            step=Event.Started.name,
            filename=storage.filename,
            **kwargs,
        )

        suffix = kwargs.pop("suffix", ".csv")
        output = str(storage.with_suffix(suffix).absolute())
        content.to_csv(output, **kwargs)

        self.debug(
            msg=f"{Event.Write.name}_csv",
            step=Event.Completed.name,
            output=output,
        )

        return output

    def _write_json(self, storage: FileStorage, content: pd.DataFrame, **kwargs) -> str:
        self.debug(
            msg=f"{Event.Write.name}_json",
            step=Event.Started.name,
            filename=storage.filename,
            uri=storage.uri,
            digest=storage.digest,
            **kwargs,
        )

        suffix = kwargs.pop("suffix", ".json")
        output = str(storage.with_suffix(suffix).absolute())
        content.to_json(output, **kwargs)

        self.debug(  # type: ignore
            msg=f"{Event.Write.name}_json",
            step=Event.Completed.name,
            output=output,
        )

        return output

    def _write_graph(self, storage: FileStorage, content: Graph, **kwargs) -> str:
        self.debug(
            msg=f"{Event.Write.name}_graph",
            step=Event.Started.name,
            filename=storage.filename,
            uri=storage.uri,
            digest=storage.digest,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=content, expected_type=Graph)

        suffix = kwargs.pop("suffix", ".json")
        output = str(storage.with_suffix(suffix).absolute())
        content.serialize(
            destination=output,
            format="json-ld",
            indent=2,
        )

        self.debug(
            msg=f"{Event.Write.name}_graph",
            step=Event.Completed.name,
            output=output,
        )

        return output

    def _write_png(self, storage: FileStorage, content: object, **kwargs) -> str:
        """Persist a PNG image, optionally applying PII redaction boxes.

        Expected kwargs (all optional unless noted):
            source_path   : str   - origin file; read when content is not an
                                    in-memory image. Required if no content
                                    object is supplied.
            redact_boxes  : list[tuple[int, int, int, int]]
                                  - (x0, y0, x1, y1) pixel rectangles filled
                                    with opaque black to obscure PII.
            replacements  : list[tuple[tuple[int, int, int, int], str]]
                                  - optional substitute strings drawn over the
                                    black rectangles in a monospace font.
            strip_metadata: bool  - default True; removes EXIF/tEXt chunks.
            suffix        : str   - default ".png".
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as e:
            raise ModuleNotFoundError(
                "PIL library is missing. Add it manually: pip install Pillow"
            ) from e

        self.debug(
            msg=f"{Event.Write.name}_png",
            step=Event.Started.name,
            filename=storage.filename,
            uri=storage.uri,
            **kwargs,
        )

        source_path = kwargs.pop("source_path", None)
        redact_boxes = kwargs.pop("redact_boxes", []) or []
        replacements = kwargs.pop("replacements", []) or []
        strip_metadata = kwargs.pop("strip_metadata", True)
        suffix = kwargs.pop("suffix", ".png")

        if isinstance(content, Image.Image):
            image = content.copy()
        elif isinstance(content, (bytes, bytearray)):
            # safe_open_bytes blocks oversized payloads, format spoofing and
            # malformed streams before Pillow decodes pixel data.
            image = safe_open_bytes(bytes(content), expected=("PNG",))
        elif source_path:
            image = safe_open(source_path, expected=("PNG",))
        else:
            reason = "PNG write requires in-memory image, bytes or source_path"
            self.error(msg=Event.Write.name, reason=reason)
            raise ValueError(reason)

        image = image.convert("RGBA" if image.mode == "RGBA" else "RGB")

        draw = ImageDraw.Draw(image)

        # Tesseract bbox 'top' rides cap-line, missing the actual glyph ascender
        # (and our č/š/ž diacritics). Pad upward more than downward.
        _PAD_TOP_RATIO = 0.18
        _PAD_BOT_RATIO = 0.06

        def _pad_box(box):
            x0, y0, x1, y1 = box
            h = y1 - y0
            pad_t = max(2, int(h * _PAD_TOP_RATIO))
            pad_b = max(1, int(h * _PAD_BOT_RATIO))
            return (x0, max(0, y0 - pad_t), x1, y1 + pad_b)

        padded = [_pad_box(b) for b in redact_boxes]
        for pbox in padded:
            draw.rectangle(pbox, fill=(0, 0, 0))

        if replacements:
            def _pick_font(box_h: int):
                # Roughly 55% of box height; clamped so labels stay legible
                # without overflowing in narrow OCR cells.
                target = max(7, min(int(box_h * 0.55), 16))
                try:
                    return ImageFont.truetype("DejaVuSans.ttf", size=target)
                except (OSError, IOError):
                    try:
                        return ImageFont.load_default(size=target)
                    except TypeError:
                        return ImageFont.load_default()

            pad_map = {tuple(rb): pb for rb, pb in zip(redact_boxes, padded)}
            for raw_box, text in replacements:
                if not text:
                    continue
                x0, y0, x1, y1 = pad_map.get(tuple(raw_box), _pad_box(raw_box))
                font = _pick_font(y1 - y0)
                try:
                    tx0, ty0, tx1, ty1 = font.getbbox(str(text))
                    th = ty1 - ty0
                except AttributeError:
                    th = y1 - y0
                cx = x0 + 2
                cy = y0 + max(0, ((y1 - y0) - th) // 2)
                draw.text((cx, cy), str(text), fill=(255, 255, 255), font=font)

        output = str(storage.with_suffix(suffix).absolute())

        save_kwargs: dict = {"format": "PNG", "optimize": True}
        if strip_metadata:
            # Writing without pnginfo discards all ancillary chunks (tEXt, iTXt,
            # zTXt, eXIf) — required for forensically clean redaction output.
            save_kwargs["pnginfo"] = None

        image.save(output, **save_kwargs)

        self.debug(
            msg=f"{Event.Write.name}_png",
            step=Event.Completed.name,
            output=output,
            boxes=len(redact_boxes),
            replacements=len(replacements),
        )

        return output

    def _write_pdf(self, storage: FileStorage, content: object, **kwargs) -> str:
        """Persist a PDF, optionally applying PII redaction spans per page.

        Expected kwargs (all optional unless noted):
            source_path      : str   - origin file; required when content is
                                       not raw bytes.
            pdf_redact_spans : list[dict] - each span is
                                       {"page": int,
                                        "bbox": (x0, y0, x1, y1),
                                        "replacement": str}
                                       bbox units are PDF points (PyMuPDF).
            strip_metadata   : bool  - default True; wipes document info and
                                       XMP metadata after redaction.
            suffix           : str   - default ".pdf".
        """
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise ModuleNotFoundError(
                "PyMuPDF library is missing. Add it manually: pip install PyMuPDF"
            ) from e

        self.debug(
            msg=f"{Event.Write.name}_pdf",
            step=Event.Started.name,
            filename=storage.filename,
            uri=storage.uri,
            **kwargs,
        )

        source_path = kwargs.pop("source_path", None)
        spans = kwargs.pop("pdf_redact_spans", []) or []
        strip_metadata = kwargs.pop("strip_metadata", True)
        suffix = kwargs.pop("suffix", ".pdf")

        if isinstance(content, (bytes, bytearray)):
            pdf = fitz.open(stream=bytes(content), filetype="pdf")
        elif source_path:
            pdf = fitz.open(source_path)
        else:
            reason = "PDF write requires bytes content or source_path"
            self.error(msg=Event.Write.name, reason=reason)
            raise ValueError(reason)

        try:
            spans_by_page: dict[int, list] = {}
            for span in spans:
                idx = int(span.get("page", 0))
                spans_by_page.setdefault(idx, []).append(span)

            for page_idx, page_spans in spans_by_page.items():
                if page_idx < 0 or page_idx >= pdf.page_count:
                    continue
                page = pdf[page_idx]
                for span in page_spans:
                    bbox = span.get("bbox")
                    if not bbox or len(bbox) != 4:
                        continue
                    rect = fitz.Rect(*bbox)
                    repl = span.get("replacement") or ""
                    page.add_redact_annot(rect, text=repl, fill=(0, 0, 0))
                page.apply_redactions()

            if strip_metadata:
                # PyMuPDF clears info-dict entries by writing None values.
                pdf.set_metadata({k: None for k in (pdf.metadata or {})})
                try:
                    pdf.del_xml_metadata()
                except Exception:
                    # XMP stream may be absent — not an error, just nothing to strip.
                    pass

            output = str(storage.with_suffix(suffix).absolute())
            pdf.save(output, garbage=4, deflate=True, clean=True)
        finally:
            pdf.close()

        self.debug(
            msg=f"{Event.Write.name}_pdf",
            step=Event.Completed.name,
            output=output,
            spans=len(spans),
        )

        return output

    # endregion private methods
