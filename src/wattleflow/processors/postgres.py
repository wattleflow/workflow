# Module Name: processors/postgress.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains processor for handling postgres records.

import pandas as pd
from uuid import uuid4
from typing import Generator
from wattleflow.core import IBlackboard, IStrategy
from wattleflow.concrete import DocumentFacade, GenericProcessor, ConnectionManager
from wattleflow.concrete.processor import T


class PostgresReadProcessor(GenericProcessor[DocumentFacade]):
    def __init__(
        self,
        strategy_audit: IStrategy,
        blackboard: IBlackboard,
        pipelines: list,
        queries: list,
        manager: ConnectionManager,
        connection_name: str,
    ):
        super().__init__(
            strategy_audit=strategy_audit,
            blackboard=blackboard,
            pipelines=pipelines,
            queries=queries,
            manager=manager,
            connection_name=connection_name,
        )
        self._current = None
        self._queries: list = queries
        self._manager: ConnectionManager = manager
        self._connection_name = connection_name
        self._iterator = self.create_iterator()

    def _read_data(self, sql):
        with self._manager.get_connection(self._connection_name) as db:
            with db.connect():
                return pd.read_sql_query(sql, db.connection)

    def create_iterator(self) -> Generator[T, None, None]:
        for sql in self._queries:
            data = self._read_data(sql)
            item = self.blackboard.create(
                processor=self,
                filename=str(uuid4()),
                content=data.to_dict(),
            )
            yield item
