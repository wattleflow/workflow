# Module name: __init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module follows the “build once, use often” principle,
supporting bespoke implementations of cryptographic strategy classes within
the Wattleflow Workflow ETL framework. It provides tools for the creation and
management of information security components, enhancing both consistency and
reusability across workflows.
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
from .documents.graph_youtube import (
    YoutubeGraph,
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
    "YoutubeGraph",
    "WriteYoutubeDocument",
]
