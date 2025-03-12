# Module Name: strategies/fernet.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete fernet strategies classes.

from cryptography.fernet import Fernet
from wattleflow.core import IStrategy

# from cryptography.hazmat.primitives import hashes
# from cryptography.hazmat.primitives.asymmetric import padding
# from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey


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
