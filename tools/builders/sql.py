# Module Name: tools/builders/sql.py
# Description: This modul contains SQL builder code for UML.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence


import re
from typing import Dict
from core.builder import UMLBuilder
from wattleflow.core import IExpression


class TableNotFound(ValueError):
    def __init__(self):
        super().__init__("Table is not found.")


class ParseSqlTable(IExpression):
    def __init__(self, **kwargs):
        self._tables: Dict[str, Dict[str, str]] = {}
        self._re_create = re.compile(
            r"""
            CREATE\s+TABLE\s+
            (?:                                       # opcionalna shema:
            (?:"(?P<schema_q>[^"]+)"|(?P<schema_u>\w+))\s*\.\s*
            )?
            (?:"(?P<table_q>[^"]+)"|(?P<table_u>\w+)) # naziv tablice (quoted ili unquoted)
            \s*\(
                (?P<cols>.*?)                         # blok kolona
            \)
            \s*;
            """,
            re.IGNORECASE | re.S | re.X,
        )

        # split po zarezu koji NIJE unutar zagrada
        self._re_split_cols = re.compile(r",\s*(?![^()]*\))", re.S)
        self._table_level = {"PRIMARY", "UNIQUE", "FOREIGN", "CONSTRAINT", "CHECK"}

    @property
    def tables(self) -> Dict[str, Dict[str, str]]:
        return self._tables

    def interpret(self, context: str) -> bool:
        for m in self._re_create.finditer(context):
            schema = m.group("schema_q") or m.group("schema_u")
            table = m.group("table_q") or m.group("table_u")
            table_name = f"{schema}.{table}" if schema else table

            cols_block = m.group("cols")
            fields: Dict[str, str] = {}

            for raw in self._re_split_cols.split(cols_block):
                line = raw.strip()
                if not line:
                    continue

                # first token (može biti ime kolone ili table-level constraint)
                parts = line.split(None, 1)
                head = parts[0].strip('"')  # ukloni navodnike s imena kolone
                rest = parts[1].strip() if len(parts) > 1 else ""

                if head.upper() in self._table_level:
                    # skip PRIMARY KEY (...), CONSTRAINT ..., CHECK (...)
                    continue

                fields[head] = rest

            self._tables[table_name] = fields

        return len(self._tables) > 0


class SQLBuilder(UMLBuilder):
    def build(self) -> None:
        expr = ParseSqlTable()

        if not expr.interpret(str(self._content)) == True:  # noqa: 712
            raise TableNotFound()

        # TODO: Use TextFileStream as a template reader
        # and move standard strings to a file template.

        uml: list = []
        uml.append("@startuml\n")
        # uml << "hide circle\n"
        uml.append("skinparam linetype ortho")
        uml.append("!pragma teoz true")

        for name, fields in expr.tables.items():
            uml.append(f"\nentity {name} {{")
            for field, spec in fields.items():
                uml.append(f"\t+ {field}: {spec}")
            uml.append("}")

        uml.append("@enduml")

        self._rendered = "\n".join(uml)
