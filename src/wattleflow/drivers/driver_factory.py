# Module name: driver_factory.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence

import logging
from abc import ABC
from typing import Optional
from urllib.parse import urlparse
from wattleflow.core.creational import IFactory
from wattleflow.constants import Event
from wattleflow.concrete import AuditException, AuditLogger, GenericDriverClass

# region URI primjeri za distribuirane sustave
# Apache Kafka

# # Broker
# kafka://broker.example.com:9092
# kafka://broker1:9092,broker2:9092,broker3:9092

# # Schema Registry
# http://schema-registry.example.com:8081

# # Kafka Connect REST API
# http://connect.example.com:8083

# # SASL/SSL
# kafka+ssl://broker.example.com:9093
# Elasticsearch

# # Single node
# http://localhost:9200
# https://elastic.example.com:9200

# # S kredencijalima
# http://user:password@elastic.example.com:9200

# # Elastic Cloud
# https://my-deployment.es.us-east-1.aws.elastic-cloud.com:9243

# # Multiple nodes
# http://node1:9200,node2:9200,node3:9200
# Apache Spark

# # Standalone
# spark://master.example.com:7077

# # YARN
# yarn://resourcemanager.example.com:8032

# # Mesos
# mesos://zk://zk1:2181,zk2:2181/mesos

# # Kubernetes
# k8s://https://k8s-apiserver.example.com:6443

# # Local (razvoj)
# local://
# local[4]://
# Apache Flink

# # JobManager REST API
# http://jobmanager.example.com:8081

# # YARN
# yarn://resourcemanager.example.com:8032

# # Kubernetes
# kubernetes://k8s-apiserver.example.com:6443
# Apache Hadoop / HDFS

# hdfs://namenode.example.com:8020/path/to/data
# hdfs://namenode:9000/user/hadoop/data

# # HA (High Availability)
# hdfs://my-ha-cluster/path/to/data

# # WebHDFS
# webhdfs://namenode.example.com:50070/path/to/data
# Apache Hive / HiveServer2

# jdbc:hive2://hiveserver.example.com:10000/default
# jdbc:hive2://hiveserver:10000/mydb;ssl=true
# jdbc:hive2://zk1:2181,zk2:2181/;serviceDiscoveryMode=zooKeeper
# Apache ZooKeeper

# zk://zk1.example.com:2181,zk2.example.com:2181,zk3.example.com:2181
# zookeeper://zk1:2181/kafka
# Apache Cassandra

# cassandra://node1.example.com:9042
# cql://user:password@cassandra.example.com:9042/keyspace

# # Driver connection string
# cassandra://node1:9042,node2:9042,node3:9042
# Apache HBase

# hbase://zk1:2181,zk2:2181,zk3:2181
# thrift://hbase.example.com:9090
# Redis

# redis://localhost:6379
# redis://user:password@redis.example.com:6379/0
# rediss://redis.example.com:6380          # SSL
# redis-sentinel://sentinel1:26379,sentinel2:26379/mymaster
# redis-cluster://node1:6379,node2:6379
# MongoDB

# mongodb://localhost:27017
# mongodb://user:password@mongo.example.com:27017/mydb
# mongodb+srv://cluster.mongodb.net/mydb  # Atlas (DNS SRV)

# # Replica Set
# mongodb://node1:27017,node2:27017,node3:27017/?replicaSet=rs0
# Apache Pulsar

# pulsar://broker.example.com:6650
# pulsar+ssl://broker.example.com:6651
# http://pulsar-admin.example.com:8080    # Admin API
# RabbitMQ

# amqp://user:password@rabbitmq.example.com:5672/vhost
# amqps://user:password@rabbitmq.example.com:5671/vhost  # SSL
# InfluxDB

# http://influxdb.example.com:8086
# https://eu-central-1-1.aws.cloud2.influxdata.com  # Cloud
# MinIO / S3-compatible

# s3://my-bucket/path/to/object
# s3a://my-bucket/path/                   # Hadoop S3A connector
# http://minio.example.com:9000/bucket
# endregion URI primjeri za distribuirane sustave

# Schemes that unambiguously identify a remote resource.
# Local paths (no scheme, or "file://") are NOT in this set.
_REMOTE_SCHEMES: frozenset = frozenset(
    {
        # HTTP / HTTPS (Elasticsearch, InfluxDB, Flink, MinIO, generic REST)
        "http",
        "https",
        # Object storage
        "s3",
        "s3a",
        "s3n",
        "gs",  # Google Cloud Storage
        "az",  # Azure Blob (abfs/wasb also common)
        "abfs",
        "abfss",
        "wasb",
        "wasbs",
        # Distributed file systems
        "hdfs",
        "webhdfs",
        "viewfs",
        # Message brokers
        "kafka",
        "kafka+ssl",
        "amqp",  # RabbitMQ
        "amqps",
        "pulsar",
        "pulsar+ssl",
        # Compute / cluster managers
        "spark",
        "yarn",
        "mesos",
        "k8s",
        "kubernetes",
        # Databases / key-value stores
        "mongodb",
        "mongodb+srv",
        "cassandra",
        "cql",
        "hbase",
        "redis",
        "rediss",
        "redis-sentinel",
        "redis-cluster",
        "jdbc",
        "postgresql",
        "postgres",
        "mysql",
        "mssql",
        "oracle",
        "clickhouse",
        # Search / analytics
        "elasticsearch",
        "opensearch",
        # Streaming / coordination
        "zk",
        "zookeeper",
        "thrift",
        # Transfer protocols
        "ftp",
        "ftps",
        "sftp",
        "ssh",
        "scp",
    }
)


# region DriverFactory
class DriverFactory(IFactory, AuditLogger, ABC):
    def __init__(
        self,
        level: int,
        handler: Optional[logging.Handler] = None,
        *args,
        **kwargs,
    ):
        IFactory.__init__(self)
        AuditLogger.__init__(self, level=level, handler=handler, *args, **kwargs)
        self.debug(
            msg=Event.Constructor.value,
            status=Event.Completed.value,
        )

    @staticmethod
    def is_remote(uri: str) -> bool:
        """Return True when *uri* points to a remote resource.

        Detection logic:
        - Parse the URI with ``urllib.parse.urlparse``.
        - A non-empty scheme that appears in ``_REMOTE_SCHEMES`` → remote.
        - No scheme, an empty scheme, or the ``file`` scheme → local.
        - An unrecognised scheme (e.g. a custom internal protocol) → local
          by default so that callers are not forced remote unexpectedly.

        Examples::

            DriverFactory.is_remote("http://elastic.example.com:9200")  # True
            DriverFactory.is_remote("s3://my-bucket/path")              # True
            DriverFactory.is_remote("kafka://broker:9092")              # True
            DriverFactory.is_remote("hdfs://namenode:8020/data")        # True
            DriverFactory.is_remote("redis://localhost:6379")           # True
            DriverFactory.is_remote("/tmp/local/path")                  # False
            DriverFactory.is_remote("file:///tmp/data")                 # False
            DriverFactory.is_remote("./relative/path")                  # False
        """
        if not uri or not isinstance(uri, str):
            return False

        parsed = urlparse(uri)
        scheme = parsed.scheme.lower()

        if not scheme:
            return False

        if scheme == "file":
            return False

        return scheme in _REMOTE_SCHEMES

    @staticmethod
    def create(
        local_path: str,
        is_remote: bool,
        normalised: bool,
        level: int,
        handler: Optional[logging.Handler] = None,
        **kwargs,
    ) -> GenericDriverClass:
        try:
            if is_remote:
                from wattleflow.drivers.http_file_system_driver import (
                    HttpFileSystemDriver,
                )

                return HttpFileSystemDriver(
                    level=level,
                    handler=handler,
                    local_path=local_path,
                    create=True,
                    normalised=normalised,
                    **kwargs,
                )
            else:
                from wattleflow.drivers.local_file_system_driver import (
                    LocalFileSystemDriver,
                )

                return LocalFileSystemDriver(
                    local_path=local_path,
                    level=level,
                    handler=handler,
                    create=False,
                    normalised=normalised,
                )
        except AuditException as e:
            raise RuntimeError(f"DriverFactory.local_driver: {e.reason}") from e
        except Exception as e:
            raise RuntimeError(f"DriverFactory.local_driver: {e}") from e


# endregion DriverFactory
