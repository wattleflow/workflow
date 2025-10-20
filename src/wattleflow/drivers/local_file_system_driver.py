# Module Name: drivers/flatfilesystem.py
# Description: This modul contains driver classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence


import os
import pandas as pd
from pathlib import Path
from wattleflow.core import IWattleflow
from wattleflow.helpers import TextNorm
from wattleflow.constants.enums import Event


class FileStorage:
    def __init__(
        self, repository_path: str, filename: str, create: bool, normalised=False
    ):
        self.origin = Path(filename)
        self.path = Path(repository_path)

        if (
            not os.path.isdir(self.path)
            and not os.access(self.path, os.R_OK)
            and not create
        ):
            raise FileNotFoundError(
                f"Path doesn't exist or not accessible: {str(self.path)}"
            )

        if create and self.path.exists() is False:
            self.path.mkdir(parents=True, exist_ok=True)

        name = (
            TextNorm.filename_from(self.origin.name) if normalised else self.origin.name
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


class LocalFileSystemDriver:
    def __init__(self, caller: IWattleflow, repository_path: str):
        self.parent = caller
        self.repository_path = repository_path

    def move_to_subdir(self, name: str, mkdir=True) -> str:
        new_repository_path = Path(self.repository_path).joinpath(name).absolute()
        if mkdir:
            if new_repository_path.exists() is False:
                new_repository_path.mkdir(parents=True)

        self.repository_path = str(new_repository_path)

        return self.repository_path

    def read(self, identifier: str) -> FileStorage:
        self.parent.debug(  # type: ignore
            msg=Event.Read.value,
            id=identifier,
        )
        return FileStorage(
            self.repository_path, filename=identifier, create=False, normalised=False
        )

    def write_csv(self, filename: str, data: pd.DataFrame, **kwargs) -> str:
        self.parent.debug(  # type: ignore
            msg=Event.Write.value,
            step=Event.Started.value,
            fnc="LocalFileSystemDriver:write_to_text",
            filename=filename,
            **kwargs,
        )

        storage = FileStorage(
            repository_path=self.repository_path,  # type: ignore
            filename=filename,
            create=True,
            normalised=True,
        )
        output = str(storage.with_suffix(".csv"))
        data.to_csv(output, **kwargs)

        self.parent.info(  # type: ignore
            msg=Event.Write.value,
            step=Event.Completed.value,
            fnc="LocalFileSystemDriver:write_csv",
            filename=storage.filename,
        )

        return str(storage.filename)

    def write_graph(self, filename: str, data: str, **kwargs) -> FileStorage:
        self.parent.debug(  # type: ignore
            msg=Event.Write.value,
            step=Event.Started.value,
            fnc="LocalFileSystemDriver:write_to_text",
            filename=filename,
            **kwargs,
        )

        storage = FileStorage(
            repository_path=self.repository_path,  # type: ignore
            filename=filename,
            create=True,
            normalised=True,
        )

        storage.filename.write_text(data)

        self.parent.info(  # type: ignore
            msg=Event.Write.value,
            step=Event.Completed.value,
            fnc="LocalFileSystemDriver:write_to_text",
            filename=storage.filename,
        )

        return storage

    def write_json(self, filename: str, data: pd.DataFrame, **kwargs) -> str:
        self.parent.debug(  # type: ignore
            msg=Event.Write.value,
            step=Event.Started.value,
            fnc="LocalFileSystemDriver:write_to_text",
            filename=filename,
            **kwargs,
        )

        storage = FileStorage(
            repository_path=self.repository_path,  # type: ignore
            filename=filename,
            create=True,
            normalised=True,
        )

        output = str(storage.with_suffix(".json"))
        data.to_json(output, **kwargs)

        self.parent.info(  # type: ignore
            msg=Event.Write.value,
            step=Event.Completed.value,
            fnc="LocalFileSystemDriver:write_to_text",
            filename=output,
        )

        return output

    def write_txt(self, filename: str, data: str, **kwargs) -> str:
        self.parent.debug(  # type: ignore
            msg=Event.Write.value,
            step=Event.Started.value,
            fnc="LocalFileSystemDriver:write_to_text",
            filename=filename,
            **kwargs,
        )

        storage = FileStorage(
            repository_path=self.repository_path,  # type: ignore
            filename=filename,
            create=True,
            normalised=True,
        )

        output = storage.with_suffix(".txt")
        output.write_text(data)

        self.parent.info(  # type: ignore
            msg=Event.Write.value,
            step=Event.Completed.value,
            fnc="LocalFileSystemDriver:write_to_text",
            output=output,
        )

        return str(output.absolute())
