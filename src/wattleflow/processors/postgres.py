# Module Name: processors/postgress.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains processor for handling postgres records.

import pandas as pd
from logging import Handler, NOTSET
from typing import Generator, Optional
from uuid import uuid4
from wattleflow.core import IBlackboard, T
from wattleflow.concrete import DocumentFacade, GenericProcessor, ConnectionManager
from wattleflow.constants import Event


class PostgresReadProcessor(GenericProcessor[DocumentFacade]):
    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: list,
        queries: list,
        manager: ConnectionManager,
        connection_name: str,
        level: int = NOTSET,
        handler: Optional[Handler] = None,
    ):
        GenericProcessor.__init__(
            self,
            blackboard=blackboard,
            pipelines=pipelines,
            queries=queries,
            manager=manager,
            connection_name=connection_name,
            level=level,
            handler=handler,
        )
        self._current = None
        self._queries: list = queries
        self._manager: ConnectionManager = manager
        self._connection_name = connection_name
        self.debug(
            msg=Event.Constructor.value,
            queries=len(queries),
            connection=self._connection_name,
        )

    def _read_data(self, sql):
        self.debug(msg="_read_data", sql=sql)
        with self._manager.get_connection(self._connection_name) as db:
            with db.connect():
                self.debug(msg=Event.Retrieving.value, connection=self._connection_name)
                return pd.read_sql_query(sql, db.connection)

    def create_iterator(self) -> Generator[T, None, None]:
        self.debug(msg=Event.Iterating.value)
        for sql in self._queries:
            data = self._read_data(sql)
            self.info(msg=Event.Iterating.value, sql=sql)
            yield self.blackboard.create(
                processor=self,
                filename=str(uuid4()),
                content=data.to_dict(),
            )
