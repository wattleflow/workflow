# Module name: helpers/datetime.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations
from datetime import datetime, timezone


class Now:
    @staticmethod
    def utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def local() -> datetime:
        return datetime.now().astimezone()

    @staticmethod
    def iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def timestamp() -> float:
        return datetime.now(timezone.utc).timestamp()
