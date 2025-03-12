# Module Name: strategies/hashlib.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete key strategies classes.

from hashlib import md5, sha224, sha256, sha384, sha512
from wattleflow.core import IStrategy


class StrategyMD5(IStrategy):
    def execute(self, value: str) -> str:
        return md5(value.encode("utf-8")).hexdigest()


class StrategySha224(IStrategy):
    def execute(self, value: str) -> str:
        return sha224(value.encode("utf-8")).hexdigest()


class StrategySha256(IStrategy):
    def execute(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()


class StrategySha384(IStrategy):
    def execute(value: str) -> str:
        return sha384(value.encode("utf-8")).hexdigest()


class StrategySha512(IStrategy):
    def execute(value: str) -> str:
        return sha512(value.encode("utf-8")).hexdigest()
