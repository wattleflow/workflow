# Module name: connections/__init__.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from .aisstream import AISStreamConnection
from .elasticsearch import ElasticSearchConnection, ElasticSearchConnectionError
from .gfw import GFWConnection
from .proxy import ProxyConnection, ProxyConnectionError
from .kafka import (
    KafkaConnectionError,
    KafkaConsumerConnection,
    KafkaProducerConnection,
)
from .postgres import PostgresConnection, PostgresError
from .sftp_paramiko import SFTPParamiko, SFTPConnectionError
from .spark import SparkConnection, SparkConnectionError

__all__ = [
    # aisstream
    "AISStreamConnection",
    # elasticsearch
    "ElasticSearchConnection",
    "ElasticSearchConnectionError",
    # gfw
    "GFWConnection",
    # http / proxy
    "ProxyConnection",
    "ProxyConnectionError",
    # kafkapo-python-ng
    "KafkaConnectionError",
    "KafkaConsumerConnection",
    "KafkaProducerConnection",
    # postgres
    "PostgresConnection",
    "PostgresError",
    # sftp
    "SFTPParamiko",
    "SFTPConnectionError",
    # spark
    "SparkConnection",
    "SparkConnectionError",
]
