# Module name: fernet.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module implements concrete classes for Fernet-based
cryptographic strategies within the Wattleflow framework. It provides secure,
symmetric encryption and decryption mechanisms, ensuring data confidentiality
and integrity through key-managed operations.
"""

from __future__ import annotations
from cryptography.fernet import Fernet
from wattleflow.core import IStrategy


class StrategyFernetGeneric(IStrategy):
    def __init__(self, key_filename: str):
        self.key_filename = key_filename
        self.key = self._load_key()

    def _generate_key(self):
        key = Fernet.generate_key()
        with open(self.key_filename, "wb") as key_file:
            key_file.write(key)
        return key

    def _load_key(self):
        try:
            with open(self.key_filename, "rb") as key_file:
                return key_file.read()
        except FileNotFoundError:
            return self._generate_key()


class StrategyFernetEncrypt(IStrategy):
    def execute(self, value: str):
        fernet = Fernet(self.key)
        return fernet.encrypt(value.encode())


class StrategyFernetDecrypt(IStrategy):
    def execute(self, value: str):
        fernet = Fernet(self.key)
        return fernet.decrypt(value).decode()
