# Module name: processors/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from .kafka import KafkaReadProcessor, KafkaWriteProcessor
from .postgres import PostgresReadProcessor
from .spark import SparkReadProcessor, SparkWriteProcessor
from .tesseract import TeseractProcessor
from .youtube import YoutubeProcessor

__all__ = [
    "KafkaReadProcessor",
    "KafkaWriteProcessor",
    "PostgresReadProcessor",
    "SparkReadProcessor",
    "SparkWriteProcessor",
    "TeseractProcessor",
    "YoutubeProcessor",
]
