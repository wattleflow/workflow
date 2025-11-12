# Module name: flatfilesystem.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
import os
import logging
import pandas as pd
from enum import Enum
from rdflib import Graph
from pathlib import Path
from typing import Generator, Optional
from wattleflow.concrete import GenericDriverClass, AuditException
from wattleflow.helpers import Attribute, Normaliser
from wattleflow.constants.enums import Event


class DriverNotFound(AuditException):
    pass


class FileTypes(Enum):
    TEXT = 1
    CSV = 2
    JSON = 3
    DATAFRAME = 4
    GRAPH = 5


class FileStorage:
    def __init__(
        self, repository_path: str, filename: str, create: bool, normalised=False
    ):
        self.origin = Path(filename)
        self.path = Path(repository_path)

        if (
            not os.path.isdir(self.path)  # noqa: W503
            and not os.access(self.path, os.R_OK)  # noqa: W503
            and not create  # noqa: W503
        ):
            raise FileNotFoundError(
                f"Path doesn't exist or not accessible: {str(self.path)}"
            )

        if create and self.path.exists() is False:
            self.path.mkdir(parents=True, exist_ok=True)

        name = (
            Normaliser.transform(self.origin.name) if normalised else self.origin.name
        )

        self.filename = self.path.joinpath(name).with_suffix(self.origin.suffix)

    @property
    def size(self) -> int:
        return os.stat(self.origin.absolute()).st_size

    def with_suffix(self, suffix: str) -> Path:
        return self.filename.with_suffix(suffix)

    def with_dir(self, directory=None, mkdir=True) -> Path:
        dir = directory if directory else self.filename.stem
        out_dir = self.path.joinpath(dir)
        if mkdir:
            out_dir.mkdir(parents=True, exist_ok=True)

        return out_dir.joinpath(self.filename.name)


class LocalFileSystemDriver(GenericDriverClass):
    def __init__(
        self,
        repository_path: str,
        level: int,
        handler: Optional[logging.Handler] = None,
        create: bool = False,
        normalised: bool = True,
    ) -> None:
        GenericDriverClass.__init__(
            self,
            level=level,
            handler=handler,
            lazy_load=False,
            allowed=["current_path", "create", "normalised", "repository_path"],
            create=create,
            normalised=normalised,
            repository_path=repository_path,
        )

    def load(self) -> None:
        self.current_path: Path = Path(self.repository_path)

    def read(self, identifier: str) -> FileStorage:
        self._repository.debug(  # type: ignore
            msg=Event.Read.value,
            id=identifier,
        )
        return FileStorage(
            repository_path=str(self.repository_path.resolve()),  # type: ignore
            filename=identifier,
            create=False,
            normalised=False,
        )

    def write(self, filename: str, ftype: FileTypes, data: object, **kwargs) -> str:
        self.debug(
            msg=Event.Write.value,
            ftype=ftype.value,
            data=type(data.__class__.__name__),
            **kwargs,
        )

        subdir = kwargs.pop("subdir", None)
        mkdir = kwargs.pop("mkdir", False)

        if subdir:
            self.__change_dir(subdir, mkdir)
        else:
            self.load()

        if ftype == FileTypes.TEXT:
            return self._write_txt(filename=filename, data=data, **kwargs)  # type: ignore
        if ftype == FileTypes.CSV:
            return self._write_csv(filename=filename, data=data, **kwargs)  # type: ignore
        elif ftype == FileTypes.JSON:
            return self._write_json(filename=filename, data=data, **kwargs)  # type: ignore
        elif ftype == FileTypes.DATAFRAME:
            return self._write_csv(filename=filename, data=data, **kwargs)  # type: ignore
        elif ftype == FileTypes.GRAPH:
            return self._write_graph(filename=filename, data=data, **kwargs)  # type: ignore
        else:
            raise TypeError("Unknown file type!")

    def search(
        self, pattern: str, case_sensitive: bool = False, recursive: bool = False
    ) -> Generator[Path, None, None]:
        search_path: Path = getattr(self, "current_path", Path(self.repository_path))
        search_path = search_path.resolve()

        self.debug(
            msg=Event.Search.value,
            step=Event.Started.value,
            pattern=pattern,
            case_sensitive=case_sensitive,
            recursive=recursive,
            search_path=str(search_path),
        )

        mask = "**/*"  # if recursive else "*/*"
        iterator = (
            search_path.rglob(mask, case_sensitive=case_sensitive)
            if recursive
            else search_path.glob(mask, case_sensitive=case_sensitive)
        )

        for path in iterator:
            if not case_sensitive:
                if pattern.lower() not in str(path.name).lower() and "*" not in pattern:
                    continue
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

        self.current_path = Path(self.repository_path).joinpath(name).absolute()  # type: ignore

        if mkdir:
            if self.current_path.exists() is False:
                self.current_path.mkdir(parents=True)

        self.debug(
            msg=Event.Move.value,
            step=Event.Completed.value,
            current_path=str(self.current_path.resolve()),
        )
        return str(self.current_path.resolve())

    # def _write_bytes(self, filename: str, data: str, **kwargs) -> int:
    #     pass

    def _write_txt(self, filename: str, data: str, **kwargs) -> str:
        self.debug(
            msg=Event.Write.value,
            step=Event.Started.value,
            filename=filename,
            **kwargs,
        )

        storage = FileStorage(
            repository_path=str(self.current_path.resolve()),
            filename=filename,
            create=True,
            normalised=True,
        )

        suffix = kwargs.get("suffix", ".txt")
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
            repository_path=str(self.current_path.resolve()),
            filename=filename,
            create=True,
            normalised=True,
        )

        suffix = kwargs.get("suffix", ".csv")
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
            repository_path=str(self.current_path.resolve()),
            filename=filename,
            create=True,
            normalised=True,
        )

        suffix = kwargs.get("suffix", ".json")
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
            repository_path=str(self.current_path.resolve()),
            filename=filename,
            create=True,
            normalised=True,
        )

        data.serialize(
            destination=str(storage.filename.absolute()),
            format="json-ld",
            indent=2,
        )

        self.debug(
            msg=Event.Write.value,
            step=Event.Completed.value,
            filename=str(storage.filename.absolute()),
        )

        return str(storage.filename.absolute())

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}:{str(self.current_path.resolve())}"  # type: ignore
