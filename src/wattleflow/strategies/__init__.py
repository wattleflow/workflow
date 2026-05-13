# Module name: strategies/documents/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
This module provides strategies for generating and storing
documents within the Wattleflow Workflow framework. It initialises
the document strategy package and exposes key classes for handling
documents.
"""


# --------------------------------------------------------------------------- #
# region imports                                                              #
# --------------------------------------------------------------------------- #

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
from .documents.graph import (
    YoutubeGraph,
    CreateYoutubeDocument,
    WriteYoutubeDocument,
)
from .documents.text import CreateTextDocument, WriteTextDocument
from .files import StrategyFilename, StrategyFilterFiles
from .loader import StrategyClassLoader

# --------------------------------------------------------------------------- #
# endregion imports                                                           #
# --------------------------------------------------------------------------- #

__all__ = [
    # text
    "CreateTextDocument",
    "WriteTextDocument",
    "StrategyBaseRSA",
    "StrategyClassLoader",
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
    # yuotube
    "YoutubeGraph",
    "CreateYoutubeDocument",
    "WriteYoutubeDocument",
]
