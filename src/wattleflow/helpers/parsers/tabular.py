# Module name: helpers/parsers/tabular.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Tabular parsers — CSV, Excel, ORC and Avro deserialisation.

Ported from ``DriverLocalStorage._read_*``: each parser turns a validated file
path into a domain object (pandas DataFrame or list[dict]). Third-party
dependencies are lazy-imported inside ``parse`` so the module stays light.
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

__all__ = ["CsvParser", "ExcelParser", "OrcParser", "AvroParser"]

# --------------------------------------------------------------------------- #
# region Parsers                                                              #
# --------------------------------------------------------------------------- #


class CsvParser(Parser):
    """Read a CSV file into a pandas DataFrame."""

    def parse(self, source: Union[str, Path], **opts: Any) -> Any:
        import pandas as pd

        return pd.read_csv(source, **opts)


class ExcelParser(Parser):
    """Read an Excel file into a pandas DataFrame."""

    def parse(self, source: Union[str, Path], **opts: Any) -> Any:
        import pandas as pd

        return pd.read_excel(source, **opts)


class OrcParser(Parser):
    """Read an ORC file into a list of row dicts."""

    def parse(self, source: Union[str, Path], **opts: Any) -> list[dict]:
        try:
            import pyarrow.orc as _orc
        except ImportError as e:
            raise ModuleNotFoundError(
                "pyarrow library is missing. Add it manually: pip install pyarrow"
            ) from e

        columns = opts.pop("columns", None)
        table = _orc.read_table(source, columns=columns)
        return table.to_pylist()


class AvroParser(Parser):
    """Read an Avro file into a list of record dicts."""

    def parse(self, source: Union[str, Path], **opts: Any) -> list[dict]:
        try:
            from fastavro import reader as _avro_reader
        except ImportError as e:
            raise ModuleNotFoundError(
                "fastavro library is missing. Add it manually: pip install fastavro"
            ) from e

        with open(source, "rb") as fh:
            return list(_avro_reader(fh))


# --------------------------------------------------------------------------- #
# endregion Parsers                                                           #
# --------------------------------------------------------------------------- #
