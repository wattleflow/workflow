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

from .dataframe import CreateDataframeDocument, WriteDataframeDocument
from .graph import CreateGraphFromHtml, WriteGraphHtmlDocument
from .text import CreateTextDocument, WriteTextDocument
from .youtube import CreateYoutubeDocument, WriteYoutubeDocument

__all__ = [
    # Create
    "CreateDataframeDocument",
    "CreateGraphFromHtml",
    "CreateTextDocument",
    "CreateYoutubeDocument",
    # Write
    "WriteDataframeDocument",
    "WriteTextDocument",
    "WriteGraphHtmlDocument",
    "WriteYoutubeDocument",
]
