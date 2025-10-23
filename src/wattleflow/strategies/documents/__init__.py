# Module Name: strategies/documents/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This module provides strategies for generating and storing TextDocuments
# within the Wattleflow Workflow framework. It initialises the document
# strategy package and exposes key classes for text document handling.


"""
This module provides strategies for generating and storing TextDocuments
within the Wattleflow Workflow framework. It initialises the document
strategy package and exposes key classes for text document handling.
"""

from .text_document import CreateTextDocument, WriteTextDocument
from .youtube_graph import CreateYoutubeDocument, WriteYoutubeDocument

__all__ = [
    "CreateTextDocument",
    "CreateYoutubeDocument",
    "WriteTextDocument",
    "WriteYoutubeDocument",
]
