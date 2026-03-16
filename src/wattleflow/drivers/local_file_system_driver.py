# Module name: local_file_system_driver.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations

import fnmatch
import os
import logging
import pandas as pd
from rdflib import Graph
from pathlib import Path
from typing import Any, Generator, Optional
from wattleflow.concrete import AuditException, GenericDriverClass
from wattleflow.decorators.preset import PresetDecorator
from wattleflow.constants.enums import Event
from wattleflow.drivers import FileStorage
from wattleflow.helpers import Attribute, FileType, Normaliser


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
        data: object,
        **kwargs,
    ) -> str:
        self.debug(
            msg=Event.Write.value,
            filename=filename,
            ftype=ftype.value,
            data=type(data).__name__,
            **kwargs,
        )

        subdir = kwargs.pop("subdir", None)
        mkdir = kwargs.pop("mkdir", False)

        if subdir:
            self.__change_dir(subdir, mkdir)
        else:
            self.load()

        if ftype == FileType.TXT:
            return self._write_txt(filename=filename, data=data, **kwargs)  # type: ignore
        if ftype == FileType.CSV:
            return self._write_csv(filename=filename, data=data, **kwargs)  # type: ignore
        if ftype == FileType.JSON:
            return self._write_json(filename=filename, data=data, **kwargs)  # type: ignore
        if ftype == FileType.GRAPH:
            return self._write_graph(filename=filename, data=data, **kwargs)  # type: ignore

        self.error(
            msg=Event.Write.value,
            error=f"unknown type: {ftype}",
            filename=filename,
            data=data,
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

    def _write_txt(self, filename: str, data: str, **kwargs) -> str:
        self.debug(
            msg=Event.Write.value,
            step=Event.Started.value,
            filename=filename,
            **kwargs,
        )

        storage = FileStorage(
            local_path=str(self.current_path.resolve()),
            uri=filename,
            create=True,
            normalised=True,
        )

        suffix = kwargs.pop("suffix", ".txt")
        output = storage.with_suffix(suffix)
        output.write_text(data)

        self.debug(
            msg=Event.Write.value,
            step=Event.Completed.value,
            output=output,
        )

        return str(output.absolute())

    def _write_csv(self, filename: str, data: pd.DataFrame, **kwargs) -> str:
        self.debug(
            msg=Event.Write.value,
            step=Event.Started.value,
            filename=filename,
            **kwargs,
        )

        storage = FileStorage(
            local_path=str(self.current_path.resolve()),
            uri=filename,
            create=True,
            normalised=True,
        )

        suffix = kwargs.pop("suffix", ".csv")
        output = str(storage.with_suffix(suffix).absolute())
        data.to_csv(output, **kwargs)

        self.debug(
            msg=Event.Write.value,
            step=Event.Completed.value,
            filename=storage.filename,
        )

        return output

    def _write_json(self, filename: str, data: pd.DataFrame, **kwargs) -> str:
        self.debug(  # type: ignore
            msg=Event.Write.value,
            step=Event.Started.value,
            filename=filename,
            **kwargs,
        )

        storage = FileStorage(
            local_path=str(self.current_path.resolve()),
            uri=filename,
            create=True,
            normalised=True,
        )

        suffix = kwargs.pop("suffix", ".json")
        output = str(storage.with_suffix(suffix))
        data.to_json(output, **kwargs)

        self.debug(  # type: ignore
            msg=Event.Write.value,
            step=Event.Completed.value,
            filename=output,
        )

        return output

    def _write_graph(self, filename: str, data: Graph, **kwargs) -> str:
        self.debug(
            msg=Event.Write.value,
            step=Event.Started.value,
            filename=filename,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=data, expected_type=Graph)

        storage = FileStorage(
            local_path=str(self.current_path.resolve()),
            uri=filename,
            create=True,
            normalised=True,
        )

        suffix = kwargs.pop("suffix", ".json")
        output = str(storage.with_suffix(suffix).absolute())
        data.serialize(
            destination=output,
            format="json-ld",
            indent=2,
        )

        self.debug(
            msg=Event.Write.value,
            step=Event.Completed.value,
            filename=output,
        )

        return output

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}:{str(self.current_path.resolve())}"  # type: ignore

    # Must be implemented if using PresetDecorator
    def __getattr__(self, name: str) -> Any:
        preset: PresetDecorator = object.__getattribute__(self, "_preset")
        return preset.__getattr__(name)


# if __name__ == "__main__":
#     import gc

#     try:
#         driver = LocalFileSystemDriver(
#             # local_path="/tmp/wattleflow_cache",
#             local_path="/mnt/d/data/csv",
#             level=logging.DEBUG,
#             create=False,
#             normalised=False,
#         )

#         # content = driver.read(uri="/mnt/d/data/csv/nsw-lga-crime-2023.csv")
#         content = driver.read(uri="/mnt/d/data/csv/hours.csv")

#         print(
#             f"""
#         filename: {content}
#         """
#         )
#     except Exception as e:
#         print(f"Caught error: {str(e)}")
#     finally:
#         gc.collect()
