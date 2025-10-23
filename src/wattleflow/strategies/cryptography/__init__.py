# Module Name: strategies/cryptography/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This module defines classes that implement various cryptographic
# strategies used within the Wattleflow framework. It provides tools for secure
# encryption, decryption, and key management within the Wattleflow Workflow framework.


"""
This module defines classes that implement various cryptographic
strategies used within the Wattleflow framework. It provides tools for
secure encryption, decryption, and key management.
"""

from .asymetric import (
    StrategyBaseRSA,
    StrategyRSAEncrypt256,
    StrategyRSADecrypt256,
    StrategyRSAEncrypt512,
    StrategyRSADecrypt512,
)
from .fernet import StrategyFernetGeneric, StrategyFernetEncrypt, StrategyFernetDecrypt
from .hashlib import (
    StrategyMD5,
    StrategySha224,
    StrategySha256,
    StrategySha384,
    StrategySha512,
)

__all__ = [
    "StrategyBaseRSA",
    "StrategyRSAEncrypt256",
    "StrategyRSADecrypt256",
    "StrategyRSAEncrypt512",
    "StrategyRSADecrypt512",
    "StrategyFernetGeneric",
    "StrategyFernetEncrypt",
    "StrategyFernetDecrypt",
    "StrategyMD5",
    "StrategySha224",
    "StrategySha256",
    "StrategySha384",
    "StrategySha512",
]
