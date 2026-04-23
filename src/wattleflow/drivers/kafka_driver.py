# Module name: kafka_driver.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# IMPORTANT:
# This driver requires the kafka-python-ng library.
# Ensure you have it installed using:
#   pip install kafka-python-ng
#
# KafkaDriver — unified persistence layer for sending and receiving Kafka messages.
# --------------------------------------------------------------------------- #


from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional
from logging import Handler, ERROR

try:
    from kafka import KafkaConsumer, KafkaProducer
    from kafka.errors import NoBrokersAvailable, NodeNotReadyError
except Exception as e:
    raise ImportError(
        f"Kafka library is required to run this code. Please install it with 'pip install kafka-python' :{str(e)}"
    ) from e

from wattleflow.concrete.connection import Connection
from wattleflow.concrete.driver import (
    DriverAction,
    GenericDriver,
    DriverState,
    DriverMetadata,
)

from wattleflow.concrete.manager import ConnectionManager
from wattleflow.concrete.exception import DriverException
from wattleflow.constants.enums import Event

# if TYPE_CHECKING:
#     from wattleflow.connections.kafka import KafkaConnection


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_TOPIC_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,249}$")


class ConnectionType(str, Enum):
    Consumer = "consumer"
    Producer = "producer"


# --------------------------------------------------------------------------- #
# Exception
# --------------------------------------------------------------------------- #


class KafkaConnectionError(DriverException):
    pass


class KafkaDriverError(DriverException):
    pass


class KafkaDriverConnectionManager:
    def __init__(self, driver: "KafkaDriver", shared_manager) -> None:
        self._driver = driver
        self._shared_manager = shared_manager
        self._clients: dict[str, object] = {}

    def _generate_group_id(self) -> str:
        return f"{self._driver.__class__.__name__}-{abs(hash(self._driver))}"

    def _get_base_connection(self, conn_name: str) -> "Connection":
        conn = self._shared_manager.get_connection(conn_name)
        if conn is None:
            raise KafkaConnectionError(
                caller=self._driver,
                error=f"Connection '{conn_name}' not found in manager",
            )
        conn._ensure_created()
        return conn

    def get_consumer(
        self, conn_name: str, topics: List[str], **overrides
    ) -> "KafkaConsumer":
        if "read" in self._clients:
            return self._clients["read"]

        from kafka import KafkaConsumer

        conn = self._get_base_connection(conn_name)
        overrides.setdefault("group_id", self._generate_group_id())
        overrides.setdefault("auto_offset_reset", "earliest")
        config = conn._build_consumer_config(**overrides)

        consumer = KafkaConsumer(**config)
        if topics:
            consumer.subscribe(topics)
        self._clients["read"] = consumer
        return consumer

    def get_producer(self, conn_name: str, **overrides) -> "KafkaProducer":
        if "write" in self._clients:
            return self._clients["write"]

        from kafka import KafkaProducer

        conn = self._get_base_connection(conn_name)
        config = conn._build_producer_config(**overrides)

        producer = KafkaProducer(**config)
        self._clients["write"] = producer
        return producer

    def invalidate(self, role: Optional[str] = None) -> None:
        if role and role in self._clients:
            self._close_client(self._clients.pop(role))
        elif role is None:
            for client in self._clients.values():
                self._close_client(client)
            self._clients.clear()

    def clear(self) -> None:
        self.invalidate()

    @staticmethod
    def _close_client(client) -> None:
        try:
            from kafka import KafkaConsumer, KafkaProducer

            if isinstance(client, KafkaConsumer):
                client.close(autocommit=True)
            elif isinstance(client, KafkaProducer):
                client.close(timeout=10)
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"KafkaDriverConnectionManager(clients={list(self._clients.keys())})"


class KafkaDriver(GenericDriver):
    ALLOWED_KWARGS = ["consumer", "producer", "topics"]

    def __init__(
        self,
        connection_name: str,
        manager: ConnectionManager = None,
        level: int = ERROR,
        handler: Optional[Handler] = None,
        **kwargs,
    ) -> None:
        kwargs.pop("allowed", None)

        if not connection_name or connection_name == "":
            raise KafkaConnectionError("KafkaDriver: connection_name must be provided!")

        GenericDriver.__init__(
            self,
            level=level,
            handler=handler,
            allowed=self.ALLOWED_KWARGS,
            connection_name=connection_name,
            manager=manager,
            **kwargs,
        )
        self._connection_name = connection_name
        self._level = level
        self._handler = handler
        self._manager = manager

        # manager: if not provied, create internally
        if not isinstance(self._manager, ConnectionManager):
            self._manager = ConnectionManager(self._level, self._handler)

        self.ensure_live()
        self.debug(
            msg=Event.Constructor.name,
            step=Event.Completed.name,
            manager=self._manager,
            connection=self._connection_name,
            topics=self.topics,
            state=self.state,
        )

    def load(self):
        self.info(
            msg="load",
            step=Event.Started.name,
            connection=self._connection_name,
            manager=self._manager,
            state=self.state.name,
        )

        if self.consumer is None or len(self.consumer) < 1:
            raise ValueError("Kafka: Consumer confiugration must be provided!")

        if self.producer is None or len(self.producer) < 1:
            raise ValueError(
                "Kafka: consumer & producer confiugration must be provided!"
            )

        if self.state != DriverState.LOADING:
            raise RuntimeError(f"Loading: state runtime error: {self.state.name}")

        try:
            # -------------------------------------------------------------------
            # consumer: create, register and subscribe -------------------------
            # -------------------------------------------------------------------
            raw_topics = self.topics or []
            if isinstance(raw_topics, str):
                raw_topics = [t.strip() for t in raw_topics.split(",") if t.strip()]
            topics = list(raw_topics)
            consumer_name = self._get_conn_name(ConnectionType.Consumer)
            self._manager.register_connection(
                KafkaConsumer(*topics, **self.consumer),
                connection_name=consumer_name,
            )
            # Kafka Conusmer nema subscribe metodu.
            # self._manager.get_connection(consumer_name).subscribe(self)

            # -------------------------------------------------------------------
            # producer: create, register and subscribe --------------------------
            # -------------------------------------------------------------------
            producer_name = self._get_conn_name(ConnectionType.Producer)
            self._manager.register_connection(
                KafkaProducer(**self.producer),
                connection_name=producer_name,
            )
            # self._manager.get_connection(producer_name).subscribe(self)
        except NoBrokersAvailable as e:
            error_msg = f"{str(e)}: no brokers available for connection '{self._connection_name}'!"
            self.error(
                msg="load",
                error=error_msg,
                connection=self._connection_name,
            )
            raise KafkaConnectionError(self, error_msg) from e
        except NodeNotReadyError as e:
            error_msg = f"Node is not ready: {str(e)} - '{self._connection_name}'!"
            self.error(
                msg="load",
                error=error_msg,
                connection=self._connection_name,
            )
            raise KafkaConnectionError(self, error_msg) from e
        except Exception as e:
            raise KafkaDriverError(caller=self, error=str(e)) from e

        self.debug(msg="load", step=Event.Completed.name)

    def close(self):
        self.debug(msg="close", step=Event.Started.name)

        if not self.can(DriverAction.UNLOAD):
            return

        try:
            # name: str = self._connection_name
            # connection: Optional[Connection] = self._manager.get_connection(name)

            consumer: KafkaConsumer = self._manager.get_connection(
                self._get_conn_name(ConnectionType.Consumer)
            )
            if consumer:
                self.debug(
                    msg="close",
                    step=Event.Disconnect.name,
                    conn=ConnectionType.Consumer.name,
                )
                # consumer.close(autocommit=True)

            producer: KafkaProducer = self._manager.get_connection(
                self._get_conn_name(ConnectionType.Producer)
            )
            if producer:
                self.debug(
                    msg="close",
                    step=Event.Disconnect.name,
                    conn=ConnectionType.Producer.name,
                )
                producer.close(timeout=10)

            self._manager.unregister_connection(
                self._get_conn_name(ConnectionType.Consumer)
            )
            self._manager.unregister_connection(
                self._get_conn_name(ConnectionType.Producer)
            )

            self.debug(msg="close", step=Event.Completed.name)
        except Exception as e:
            error = f"{str(e)}: caught while closing {self!r}!"
            self.error(
                msg="close",
                error=error,
                connection=self._connection_name,
                manager=self._manager,
            )

    def read(self, uri: str, **kwargs) -> list:
        self.debug(msg="read", step=Event.Started.name, uri=uri, kwargs=kwargs)

        poll_timeout_ms: int = kwargs.get("poll_timeout_ms", 5000)
        max_records: int = kwargs.get("max_records", 100)
        topic_filter: Optional[str] = uri or None

        self.debug(
            msg="read",
            step=Event.Started.name,
            topic_filter=topic_filter or "(all)",
            poll_timeout_ms=poll_timeout_ms,
            max_records=max_records,
        )

        consumer_name = self._get_conn_name(ConnectionType.Consumer)
        consumer: KafkaConsumer = self._manager.get_connection(consumer_name)

        if not isinstance(consumer, KafkaConsumer):
            raise KafkaDriverError(
                caller=self,
                error=f"read: unexpected connection type: {consumer.__class__.__name__!r}!",
            )

        self.debug(msg="read", step=Event.Reading.name, consumer=consumer_name)

        messages = []
        try:
            raw = consumer.poll(timeout_ms=poll_timeout_ms, max_records=max_records)
            for tp, msgs in raw.items():
                if topic_filter and tp.topic != topic_filter:
                    continue
                for msg in msgs:
                    messages.append(
                        {
                            "topic": msg.topic,
                            "partition": msg.partition,
                            "offset": msg.offset,
                            "key": msg.key.decode("utf-8") if msg.key else None,
                            "value": msg.value,
                            "timestamp": msg.timestamp,
                        }
                    )
        except KafkaConnectionError as e:
            error = f"{self.name!r} connection error caught while handling read request: {str(e)}!"
            raise KafkaDriverError(caller=self, error=error) from e
        except Exception as e:
            error = f"{self.name!r} unexpected exception caught while handling read request: {str(e)}!"
            raise KafkaDriverError(caller=self, error=error) from e

        self.debug(msg="read", step=Event.Completed.name, count=len(messages))
        return messages

    def write(self, uri: str, **kwargs) -> str:
        self.debug(msg="write", step=Event.Started.name, uri=uri, kwargs=kwargs)

        topic: str = kwargs.get("topic") or uri
        data = kwargs.get("data")
        key = kwargs.get("key")
        flush_timeout: int = kwargs.get("flush_timeout", 10)

        if not topic:
            raise KafkaDriverError(caller=self, error="write: 'topic' is required!")
        if data is None:
            raise KafkaDriverError(caller=self, error="write: 'data' is required!")

        if isinstance(key, str):
            key = key.encode("utf-8")

        value: bytes = data if isinstance(data, bytes) else str(data).encode("utf-8")

        self.debug(
            msg="write",
            step=Event.Started.name,
            topic=topic,
            key=key,
            value_size=len(value),
        )

        producer_name = self._get_conn_name(ConnectionType.Producer)
        producer: KafkaProducer = self._manager.get_connection(producer_name)

        if not isinstance(producer, KafkaProducer):
            raise KafkaDriverError(
                caller=self,
                error=f"write: unexpected connection type: {producer.__class__.__name__!r}!",
            )

        self.debug(msg="write", step=Event.Writing.name, producer=producer_name)

        try:
            future = producer.send(topic, key=key, value=value)
            producer.flush(timeout=flush_timeout)
            record = future.get(timeout=flush_timeout)
        except KafkaConnectionError as e:
            error = f"{self.name!r} connection error caught while handling write request: {str(e)}!"
            raise KafkaDriverError(caller=self, error=error) from e
        except Exception as e:
            error = f"{self.name!r} unexpected exception caught while handling write request: {str(e)}!"
            raise KafkaDriverError(caller=self, error=error) from e

        result_uri = f"kafka://{topic}/{record.partition}/{record.offset}"

        self.debug(
            msg="write",
            step=Event.Completed.name,
            topic=topic,
            partition=record.partition,
            offset=record.offset,
            uri=result_uri,
        )

        return result_uri

    def metadata(self) -> DriverMetadata:
        try:
            from kafka import __version__ as _kafka_version
        except Exception:
            _kafka_version = "unknown"

        return DriverMetadata(
            name=self.__class__.__name__,
            version=_kafka_version,
            protocol="kafka",
            capabilities=["read", "write"],
        )

    def update(self, event: Event, **kwargs) -> None:
        event_name = event.name if hasattr(event, "name") else str(event)
        self.debug(msg="update", step=Event.Started.name, event=event_name)

        connection_name = kwargs.get("connection_name", self._connection_name)
        state = kwargs.get("state", "")
        error = kwargs.get("error", "")

        if error:
            self.error(
                msg="update",
                event=event_name,
                connection_name=connection_name,
                error=error,
                state=state,
            )
        elif event in (Event.Disconnected, Event.Disconnecting):
            self.warning(
                msg="update",
                event=event_name,
                connection_name=connection_name,
                state=state,
            )
        else:
            self.debug(
                msg="update",
                event=event_name,
                connection_name=connection_name,
                state=state,
            )

        self.debug(msg="update", step=Event.Completed.name)

    def _get_conn_name(self, conn_type: ConnectionType) -> str:
        return f"{self.name}-{id(self)}-{conn_type.name}"


# endregion KafkaDriver


# region IZBRISI


# Producer-only params (not shared with consumer in kafka-python)
# _PRODUCER_ONLY_KEYS = frozenset(
#     {
#         "acks",
#         "batch_size",
#         "bootstrap_topics_filter",
#         "buffer_memory",
#         "compression_type",
#         "connection_timeout_ms",
#         "key_serializer",
#         "linger_ms",
#         "max_block_ms",
#         "max_request_size",
#         "partitioner",
#         "retries",
#         "value_serializer",
#     }
# )

# # Consumer-only params (not shared with producer in kafka-python)
# _CONSUMER_ONLY_KEYS = frozenset(
#     {
#         "auto_commit_interval_ms",
#         "auto_offset_reset",
#         "check_crcs",
#         "consumer_timeout_ms",
#         "coordinator",
#         "default_offset_commit_callback",
#         "enable_auto_commit",
#         "exclude_internal_topics",
#         "fetch_max_bytes",
#         "fetch_max_wait_ms",
#         "fetch_min_bytes",
#         "group_id",
#         "group_instance_id",
#         "heartbeat_interval_ms",
#         "key_deserializer",
#         "leave_group_on_close",
#         "legacy_iterator",
#         "max_partition_fetch_bytes",
#         "max_poll_interval_ms",
#         "max_poll_records",
#         "metric_group_prefix",
#         "partition_assignment_strategy",
#         "session_timeout_ms",
#         "value_deserializer",
#     }
# )

# # Shared operational params (both producer and consumer, but not connection-level)
# _SHARED_OPERATIONAL_KEYS = frozenset(
#     {
#         "max_in_flight_requests_per_connection",
#         "metadata_max_age_ms",
#         "metric_reporters",
#         "metrics_num_samples",
#         "metrics_sample_window_ms",
#         "retry_backoff_ms",
#     }
# )

# # Keys to pass as overrides when creating a producer connection
# _PRODUCER_OVERRIDE_KEYS = _PRODUCER_ONLY_KEYS | _SHARED_OPERATIONAL_KEYS

# # Keys to pass as overrides when creating a consumer connection
# _CONSUMER_OVERRIDE_KEYS = _CONSUMER_ONLY_KEYS | _SHARED_OPERATIONAL_KEYS

# ALLOWED_KWARGS = [
#     # Framework / driver-level
#     "connection_name",
#     "flush_timeout",
#     "manager",
#     "kafka_conn_managermax_records",
#     "topic",
#     "topics",
#     "poll_timeout_ms",
# ] + sorted(_PRODUCER_ONLY_KEYS | _CONSUMER_ONLY_KEYS | _SHARED_OPERATIONAL_KEYS)


# class KafkaDriverOLD(GenericDriver):
#     def __init__(self, allowed=ALLOWED_KWARGS, **kwargs) -> None:
#         GenericDriver.__init__(self, allowed=allowed, **kwargs)
#         self._internal_manager: Optional[KafkaDriverConnectionManager] = None

#     def _get_internal_manager(self) -> KafkaDriverConnectionManager:
#         if self._internal_manager is None:
#             self._internal_manager = KafkaDriverConnectionManager(self, self.manager)
#         return self._internal_manager

#     def __del__(self) -> None:
#         if self._internal_manager is not None:
#             try:
#                 self._internal_manager.clear()
#             except Exception:
#                 pass

#     # region GenericDriver API

#     def load(self) -> None:
#         self.debug(msg="load", step=Event.Started.name)

#         # probe: connection_name
#         if not self.connection_name:
#             raise KafkaDriverError(
#                 caller=self,
#                 error=("KafkaDriver: 'connection_name' is required."),
#                 calledby="load",
#             )

#         conn = self.manager.get_connection(self.connection_name)

#         if conn is None:
#             raise KafkaConnectionError(
#                 caller=self,
#                 error=("KafkaDriver: 'conection:{self.connection_name}' is not found!"),
#                 calledby="load",
#             )

#         conn.subscribe(self)

#         self._loaded = True

#         self.debug(msg="load", step=Event.Completed.name, conn=conn)

#     def write(self, uri: str, data: object, **kwargs) -> str:
#         self.debug(
#             msg=Event.Write.name,
#             step=Event.Started.name,
#             uri=uri,
#             data=type(data),
#             size=len(str(data)),
#             **kwargs,
#         )

#         # topic
#         topic: str = kwargs.get("topic", None)
#         if not topic:
#             raise KafkaDriverError(
#                 caller=self,
#                 error="KafkaDriver.write: topic is required.",
#             )
#         if not _TOPIC_NAME_RE.match(topic):
#             raise KafkaDriverError(
#                 caller=self,
#                 error=f"Invalid topic name '{topic}'. Allowed characters: [a-zA-Z0-9._-], max 249 characters.",  # noqa: E501
#             )

#         # key
#         raw_key = kwargs.get("key")
#         key: Optional[bytes] = raw_key.encode("utf-8") if isinstance(raw_key, str) else raw_key

#         # data
#         value: bytes = self._serialise(data)

#         # timeout
#         flush_timeout: int = int(self.flush_timeout or 10)

#         self.debug(
#             msg=Event.Write.name,
#             step=Event.Started.name,
#             topic=topic,
#             size=len(value),
#             key=raw_key,
#         )

#         try:
#             record = self._execute_write(topic, key, value, flush_timeout)
#         except KafkaConnectionError as e:
#             if not self._try_reconnect(self.write_connection or self.connection_name):
#                 raise
#             self.warning(
#                 msg=Event.Write.name,
#                 step="reconnect",
#                 error=str(e),
#                 topic=topic,
#             )
#             record = self._execute_write(topic, key, value, flush_timeout)
#         except KafkaDriverError:
#             raise
#         except Exception as e:
#             raise KafkaDriverError(
#                 caller=self,
#                 error=f"KafkaDriver.write error for topic='{topic}': {e}",
#             ) from e

#         result_uri = f"kafka://{topic}/{record.partition}/{record.offset}"

#         self.debug(
#             msg=Event.Write.name,
#             step=Event.Completed.name,
#             uri=result_uri,
#         )

#         return result_uri

#     def read(self, uri: str, **kwargs) -> List[dict]:
#         self.debug(msg=Event.Read.name, step=Event.Started.name, uri=uri, **kwargs)

#         poll_timeout_ms = int(self.poll_timeout_ms or 5000)
#         max_records = int(self.max_records or 100)

#         raw_topics = self.topics or []
#         if isinstance(raw_topics, str):
#             raw_topics = [t.strip() for t in raw_topics.split(",") if t.strip()]
#         topics: List[str] = list(raw_topics)

#         self.debug(
#             msg=Event.Read.name,
#             step=Event.Started.name,
#             topics=topics,
#             topic_filter=uri or "(all)",
#             poll_timeout_ms=poll_timeout_ms,
#         )

#         try:
#             messages = self._execute_read(topics, uri, poll_timeout_ms, max_records)
#         except KafkaConnectionError as e:
#             if not self._try_reconnect(self.connection_name):
#                 raise
#             self.warning(
#                 msg=Event.Read.name,
#                 step="reconnect",
#                 error=str(e),
#                 topic_filter=uri or "(all)",
#             )
#             messages = self._execute_read(topics, uri, poll_timeout_ms, max_records)
#         except KafkaDriverError:
#             raise
#         except Exception as e:
#             raise KafkaDriverError(
#                 caller=self,
#                 error=f"KafkaDriver.read error: {e}",
#             ) from e

#         self.debug(
#             msg=Event.Read.name,
#             step=Event.Completed.name,
#             count=len(messages),
#             topic_filter=uri or "(all)",
#         )

#         return messages

#     def update(self, owner, **kwargs) -> None:
#         new_conn = kwargs.get("new_connection")
#         if new_conn is None:
#             return

#         self.debug(msg="connection_changed", new_conn=new_conn.connection_name)

#         # Pauziramo I/O dok ne reinicijaliziramo klijenta
#         old_state = self._state
#         self._state = DriverState.LOADING

#         try:
#             # Reinicijaliziramo klijenta s novom konekcijom
#             self._client = new_conn.get_client()
#             self._state = DriverState.LIVE
#         except Exception as e:
#             self._state = DriverState.DEGRADED
#             self.error(msg="hot_swap_failed", error=str(e))

#     # endregion GenericDriver API

#     def search(self, pattern: str, **kwargs) -> Generator[str, None, None]:
#         conn_name = self.write_connection or self.connection_name
#         if not conn_name:
#             raise KafkaDriverError(
#                 caller=self,
#                 error="KafkaDriver.search: no connection is configured.",
#             )

#         self.debug(msg=Event.Search.name, step=Event.Started.name, pattern=pattern)

#         conn = self.manager.get_connection(conn_name)
#         try:
#             topics = conn.list_topics()
#         except KafkaConnectionError:
#             raise
#         except Exception as e:
#             raise KafkaDriverError(
#                 caller=self,
#                 error=f"search: error fetching topics: {e}",
#             ) from e

#         for topic in topics:
#             if self._matches(topic, pattern):
#                 yield topic

#         self.debug(msg=Event.Search.name, step=Event.Completed.name)

#     # region IGNORE
#     # def _ensure_topics(self, topics: List[dict], **defaults) -> None:
#     #     if not self.write_connection:
#     #         raise KafkaDriverError(
#     #             caller=self,
#     #             error="KafkaDriver.ensure_topics: 'write_connection' is not configured.",
#     #         )
#     #     conn = self.manager.get_connection(self.write_connection)
#     #     conn.ensure_topics(topics=topics, **defaults)
#     # endregion IGNORE

#     # ---------------------------------------------------------------------- #
#     # region Internal helpers
#     # ---------------------------------------------------------------------- #

#     def _try_reconnect(self, conn_name: str) -> bool:
#         self.debug(
#             msg="_try_reconnect",
#             step=Event.Started.name,
#             conn_name=conn_name,
#         )
#         conn = self.manager.get_connection(conn_name)
#         if conn.state == State.Unconectable:
#             self.error(
#                 msg=Event.Connection.name,
#                 step="reconnect_skipped",
#                 error="Connection is unconectable — reconnect not possible.",
#                 connection_name=conn_name,
#             )
#             return False

#         try:
#             conn.disconnect()
#             conn.create_connection()
#             self._get_internal_manager().clear()
#             self.info(
#                 msg="_try_reconnect",
#                 step=Event.Completed.name,
#                 connection_name=conn_name,
#                 state=conn.state.name,
#             )
#             return True
#         except Exception as e:
#             self.error(
#                 msg=Event.Connection.name,
#                 step="reconnect_failed",
#                 error=str(e),
#                 connection_name=conn_name,
#             )
#             return False

#     def _collect_overrides(self, keys: frozenset) -> dict:
#         preset = object.__getattribute__(self, "_preset")
#         return {k: v for k, v in preset._values.items() if k in keys and v is not None}

#     def _execute_write(self, topic: str, key, value: bytes, flush_timeout: int):
#         conn_name = self.connection_name
#         if not conn_name:
#             raise KafkaDriverError(
#                 caller=self,
#                 error="KafkaDriver._execute_write: connection is not configured",
#             )

#         mgr = self._get_internal_manager()
#         overrides = self._collect_overrides(_PRODUCER_OVERRIDE_KEYS)
#         self.debug(
#             msg="_execute_write",
#             topic=topic,
#             key=key,
#             value_size=len(value),
#         )

#         producer = mgr.get_producer(conn_name, **overrides)
#         future = producer.send(topic, key=key, value=value)
#         producer.flush()
#         return future.get(timeout=flush_timeout)

#     def _execute_read(
#         self,
#         topics: List[str],
#         uri: str,
#         poll_timeout_ms: int,
#         max_records: int,
#     ) -> List[dict]:
#         conn_name = self.connection_name
#         if not conn_name:
#             raise KafkaDriverError(
#                 caller=self,
#                 error="KafkaDriver._execute_read: 'connection_name' not configured",
#             )

#         mgr = self._get_internal_manager()
#         overrides = self._collect_overrides(_CONSUMER_OVERRIDE_KEYS)
#         messages: List[dict] = []

#         self.debug(
#             msg="_execute_read",
#             topics=topics,
#             topic_filter=uri or "(all)",
#         )

#         consumer = mgr.get_consumer(conn_name, topics, **overrides)
#         while True:
#             raw = consumer.poll(timeout_ms=poll_timeout_ms, max_records=max_records)
#             if not raw:
#                 break
#             for tp, msgs in raw.items():
#                 if uri and tp.topic != uri:
#                     continue
#                 for msg in msgs:
#                     messages.append(self._deserialise(msg))
#         return messages

#     def __repr__(self) -> str:
#         conn_name: str = self.connection_name or "<none>"
#         return f"{self.__class__.__name__}:{conn_name}"

#     # endregion Internal helpers

#     # ---------------------------------------------------------------------- #
#     # region Static helpers
#     # ---------------------------------------------------------------------- #

#     @staticmethod
#     def _serialise(data: object) -> bytes:
#         if isinstance(data, bytes):
#             return data
#         if isinstance(data, str):
#             return data.encode("utf-8")
#         return json.dumps(data, default=str).encode("utf-8")

#     @staticmethod
#     def _deserialise(msg) -> dict:
#         raw = msg.value
#         content: Any = {}
#         if raw:
#             try:
#                 content = json.loads(raw.decode("utf-8"))
#             except (ValueError, UnicodeDecodeError):
#                 content = {"raw": raw.decode("utf-8", errors="replace")}

#         return {
#             "id": f"{msg.topic}-{msg.partition}-{msg.offset}",
#             "topic": msg.topic,
#             "partition": msg.partition,
#             "offset": msg.offset,
#             "key": msg.key.decode("utf-8") if msg.key else None,
#             "timestamp": msg.timestamp,
#             "content": content,
#         }

#     @staticmethod
#     def _matches(name: str, pattern: str) -> bool:
#         if not pattern or pattern == "*":
#             return True
#         if any(c in pattern for c in ("*", "?", "[")):
#             return fnmatch.fnmatchcase(name.lower(), pattern.lower())
#         return pattern.lower() in name.lower()

#     # endregion Static helpers

# endregion IZBRISI
