# Module Name: tools/core/builder.py
# Description: This modul contains UML Builder classes.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence


from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from wattleflow.core import IBuilder, IWattleflow
from wattleflow.helpers import TextFileStream


class UMLBuilder(IBuilder, ABC):
    def __init__(
        self,
        caller: IWattleflow,
        filename: str,
        encoding: str = "utf-8",
        list_of_macros: Optional[List] = None,
    ):
        self._caller: IWattleflow = caller
        self._parts: Dict[str, list] = {}

        self.debug(
            "UMLBuilder.constructor",
            filename=filename,
            encoding=encoding,
            list_of_macros=list_of_macros,
        )

        self._rendered: str = ""
        self._content: TextFileStream = TextFileStream(
            file_path=filename,
            encoding=encoding,
            list_of_macros=list_of_macros,
        )

        self.debug(
            msg="UMLBuilder.constructor",
            content=repr(self._content),
            status="done",
        )

    def debug(self, msg: str, **kwargs) -> None:
        if hasattr(self._caller, "debug"):
            self._caller.debug(msg=msg, **kwargs)  # type: ignore

    @property
    def rendered(self) -> str:
        return str(self._rendered)

    @abstractmethod
    def build(self) -> None: ...  # noqa: E704
