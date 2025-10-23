# Module Name: strategies/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This module encompasses a set of strategies designed to ensure effective
# data protection within the Wattleflow Workflow framework. These strategies represent
# a key element in maintaining information security and form an essential component
# of the Wattleflow Workflow system.

"""
Description: This module encompasses a set of strategies designed to ensure effective
data protection within the Wattleflow Workflow framework. These strategies represent
a key element in maintaining information security and form an essential component
of the Wattleflow Workflow system.
"""

from .documents.text_document import CreateTextDocument
from .cryptography.asymetric import (
    StrategyBaseRSA,
    StrategyRSAEncrypt256,
    StrategyRSADecrypt256,
    StrategyRSAEncrypt512,
    StrategyRSADecrypt512,
)
from .cryptography.hashlib import (
    StrategyMD5,
    StrategySha224,
    StrategySha256,
    StrategySha384,
    StrategySha512,
)
from .cryptography.fernet import (
    StrategyFernetGeneric,
    StrategyFernetEncrypt,
    StrategyFernetDecrypt,
)
from .files import StrategyFilename, StrategyFilterFiles
from .loader import StrategyClassLoader
from .documents.youtube_graph import (
    CreateYoutubeDocument,
    WriteYoutubeDocument,
)

__all__ = [
    "CreateTextDocument",
    "CreateYoutubeDocument",
    "StrategyBaseRSA",
    "StrategyRSAEncrypt256",
    "StrategyRSADecrypt256",
    "StrategyRSAEncrypt512",
    "StrategyRSADecrypt512",
    "StrategyFernetGeneric",
    "StrategyFernetEncrypt",
    "StrategyFernetDecrypt",
    "StrategyFilename",
    "StrategyFilterFiles",
    "StrategyMD5",
    "StrategySha224",
    "StrategySha256",
    "StrategySha384",
    "StrategySha512",
    "StrategyClassLoader",
    "WriteYoutubeDocument",
]
