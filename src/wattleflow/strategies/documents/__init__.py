# Module name: __init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


"""
Description: This module provides strategies for generating and storing TextDocuments
within the Wattleflow Workflow framework. It initialises the document
strategy package and exposes key classes for text document handling.
"""


from .text_document import CreateTextDocument, WriteTextDocument
from .graph_youtube import CreateYoutubeDocument, WriteYoutubeDocument

__all__ = [
    "CreateTextDocument",
    "CreateYoutubeDocument",
    "WriteTextDocument",
    "WriteYoutubeDocument",
]
