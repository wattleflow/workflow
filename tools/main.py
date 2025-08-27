# Module Name: tools/main.py
# Description: This modul contains SQL UML Builder class.
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

import sys
import argparse
import pathlib
from abc import ABC
from logging import NOTSET, Handler
from typing import Optional
from core.builder import UMLBuilder
from builders.sql import SQLBuilder, TableNotFound
from wattleflow.concrete import StrategyGenerate


class BuilderNotFound(ValueError):
    pass


class UMLStrategy(StrategyGenerate, ABC):
    def __init__(
        self,
        filename: str,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
        **kwargs,
    ):
        StrategyGenerate.__init__(self, level=level, handler=handler, **kwargs)
        self.content: str = ""
        self.filename: pathlib.Path = pathlib.Path(filename)

    def _find_builder(self) -> UMLBuilder:
        if self.filename.suffix.lower() in [".sql"]:
            return SQLBuilder(
                caller=self,
                filename=self.filename.name,
            )

        raise BuilderNotFound(f"Unknown extension: [{self.filename.suffix}]")

    def execute(self, **kwargs):
        builder = self._find_builder()
        builder.build()
        print(builder.rendered)


# ---------------------------- CLI entrypoint ----------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="uml", description="Generate UML from given filename."
    )
    parser.add_argument(
        "filename",
        help="Path to the source code filename.",
    )
    parser.add_argument(
        "--log-level",
        default="NOTSET",
        help="Logging level (eg NOTSET, INFO, DEBUG, WARNING, ERROR).",
    )

    args = parser.parse_args(argv)
    import logging

    level = getattr(logging, str(args.log_level).upper(), NOTSET)

    try:
        UMLStrategy(filename=args.filename, level=level).execute()
        return 0
    except FileNotFoundError as e:
        print(f"Error: File not found: {e}", file=sys.stderr)
        return 2
    except TableNotFound as e:
        print(f"Error while parsing sql file. [{e}]", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"Error while generating UML. {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
