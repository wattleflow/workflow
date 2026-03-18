# Module name: local_file_system_driver.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations

import fnmatch
import logging
import pandas as pd
from rdflib import Graph
from pathlib import Path
from typing import Any, Generator, Optional
from wattleflow.concrete import AuditException, GenericDriverClass
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.constants.enums import Event
from wattleflow.drivers import FileStorage
from wattleflow.helpers.attribute import Attribute
from wattleflow.helpers.filetypes import FileType


class LocalFileSystemDriver(GenericDriverClass):
    def __init__(
        self,
        local_path: str,
        level: int,
        handler: Optional[logging.Handler] = None,
        create: bool = False,
        normalised: bool = True,
    ) -> None:
        __allowed__ = ["current_path", "create", "local_path", "normalised"]
        GenericDriverClass.__init__(
            self,
            level=level,
            handler=handler,
            lazy_load=False,
            allowed=__allowed__,
            create=create,
            normalised=normalised,
            local_path=Path(local_path),
        )
        self.debug(
            msg=Event.Constructor.value,
            allowed=__allowed__,
            create=create,
            normalised=normalised,
            local_path=local_path,
        )
        if Path(local_path).is_dir() is False:
            if not create:
                reason = f"local_path should be directory: {local_path!r}"
                self.error(
                    msg=Event.Constructor.value, reason=reason, local_path=local_path
                )
                raise RuntimeError(reason)
            Path(local_path).mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        self.current_path: Path = self.local_path

    def read(self, uri: str, **kwargs) -> Any:
        _uri = Path(uri).resolve()
        _base = Path(self.local_path).resolve()
        if not _uri.is_relative_to(_base):
            reason = f"Access denied: path outside base directory: {str(uri)!r}"
            self.error(msg=Event.Read.value, uri=uri, reason=reason)
            raise PermissionError(reason)
        try:
            filetype = FileType.detect(str(_uri))
            self.debug(
                Event.Read.value,
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
            self.error(msg=Event.Read.value, uri=uri, error=e.reason)
            raise
        except Exception as e:
            self.error(msg=Event.Read.value, uri=uri, error=str(e))
            raise AuditException(self, error=str(e), uri=uri)

    def write(
        self,
        uri: str,
        filename: str,
        ftype: FileType,
        content: object,
        **kwargs,
    ) -> str:
        self.debug(
            msg=Event.Write.value,
            uri=uri,
            filename=filename,
            ftype=ftype.value,
            content=type(content).__name__,
            **kwargs,
        )

        mkdir = kwargs.pop("mkdir", False)
        subdir = kwargs.pop("subdir", None)

        if subdir:
            self.__change_dir(subdir, mkdir)
        else:
            self.load()

        storage = FileStorage(
            local_path=str(self.current_path.resolve()),
            uri=filename,
            create=self.create,
            normalised=self.normalised,
        )

        if ftype == FileType.TXT:
            return self._write_txt(storage=storage, content=content, **kwargs)
        if ftype == FileType.CSV or ftype == FileType.DATAFRAME:
            return self._write_csv(storage=storage, content=content, **kwargs)
        if ftype == FileType.JSON:
            return self._write_json(storage=storage, content=content, **kwargs)
        if ftype == FileType.GRAPH:
            return self._write_graph(storage=storage, content=content, **kwargs)

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
        search_path: Path = getattr(self, "current_path", Path(self.local_path))
        search_path = search_path.resolve()

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
            msg=Event.Search.value,
            step=Event.Completed.value,
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

        self.current_path = _resolved  # type: ignore

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
            msg=Event.Write.value,
            step=Event.Started.value,
            filename=storage.filename,
            **kwargs,
        )

        suffix = kwargs.pop("suffix", ".csv")
        output = str(storage.with_suffix(suffix).absolute())
        content.to_csv(output, **kwargs)

        self.debug(
            msg=Event.Write.value,
            step=Event.Completed.value,
            output=output,
        )

        return output

    def _write_json(self, storage: FileStorage, content: pd.DataFrame, **kwargs) -> str:
        self.debug(  # type: ignore
            msg=Event.Write.value,
            step=Event.Started.value,
            filename=storage.filename,
            uri=storage.uri,
            digest=storage.digest,
            **kwargs,
        )

        suffix = kwargs.pop("suffix", ".json")
        # FIX: v0.0.0.62 - 26/3/17 - Added .absolute() to match _write_csv(); previously
        # the path was resolved relative to the current working directory, which could
        # silently change meaning if CWD shifted during the process lifetime.
        output = str(storage.with_suffix(suffix).absolute())
        content.to_json(output, **kwargs)

        self.debug(  # type: ignore
            msg=Event.Write.value,
            step=Event.Completed.value,
            output=output,
        )

        return output

    def _write_graph(self, storage: FileStorage, content: Graph, **kwargs) -> str:
        self.debug(
            msg=Event.Write.value,
            step=Event.Started.value,
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
            msg=Event.Write.value,
            step=Event.Completed.value,
            output=output,
        )

        return output

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}:{str(self.current_path.resolve())}"  # type: ignore

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)

    # endregion private methods
