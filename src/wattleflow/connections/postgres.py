# Module Name: core/connection/postgress_alchemy.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete postgres connection class.

from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine.base import Engine  # Connection
from wattleflow.core import IObserver, IStrategy
from wattleflow.concrete.connection import (
    GenericConnection,
    Operation,
    Settings,
)
from wattleflow.helpers.streams import TextStream
from wattleflow.constants.enums import Events
from wattleflow.constants.keys import (
    KEY_DATABASE,
    KEY_HOST,
    KEY_PASSWORD,
    KEY_PORT,
    KEY_USER,
    # KEY_SCHEMA,
)

# Za rad s Engine i konekcijama
#     create_engine() - Kreira Engine objekat za komunikaciju s bazom podataka.
#     connect() - Otvara novu konekciju prema bazi.
#     dispose() - Gasi sve resurse povezane s Engine objektom.
#     begin() - Započinje transakciju.
#     execute() - Izvršava SQL izraz.
#     raw_connection() - Dohvata sirovu konekciju na nižem nivou.

# Za rad s transakcijama i sesijama
#     Session() - Kreira sesiju za upravljanje transakcijama.
#     add() - Dodaje instancu objekta u sesiju.
#     commit() - Potvrđuje (commit) trenutnu transakciju.
#     rollback() - Poništava (rollback) trenutnu transakciju.
#     close() - Zatvara sesiju.
#     flush() - Sinhronizira promene u memoriji sa bazom bez commit.

# ORM metode
#     query() - Izvrsava upite prema ORM modelima.
#     filter() - Primijenjuje filtere na upit.
#     all() - Dohvaca sve rezultate upita.
#     first() - Dohvaca prvi rezultat upita.
#     delete() - Briše objekte iz baze.
#     update() - Ažurira objekte u bazi.

# Dohvatavanje metapodataka
#     MetaData() - Kreira metapodatke za baze.
#     Table() - Definira ili reflektira tablicu iz baze.
#     Column() - Definira kolonu u tabeli.


class PostgresConnection(GenericConnection):
    def __init__(self, strategy_audit: IStrategy, manager: IObserver, **settings):
        self._engine: Optional[Engine] = None
        super().__init__(strategy_audit, manager, **settings)
        self._engine: Engine = None
        self._driver: str = "<driver>"
        self._connection: Engine = None
        self._apilevel: str = "<apilevel>"
        self._version: str = "<version>"
        self._publisher: str = "<publisher>"
        self._database: str = "<database>"
        self._initialise(**settings)

    @property
    def engine(self) -> Engine:
        return self._engine

    def create_conenction(self, **settings):
        allowed = [
            KEY_DATABASE,
            KEY_HOST,
            KEY_PASSWORD,
            KEY_PORT,
            KEY_USER,
        ]

        self._settings = Settings(allowed, allowed, **settings)
        uri = "postgresql://{}:{}@{}:{}/{}".format(
            self._settings.user,
            self._settings.password,
            self._settings.host,
            self._settings.port,
            self._settings.database,
        )

        self._engine = create_engine(uri)
        self._connection = self._engine.connect()
        result = self._connection.execute(text("SELECT version();"))
        self._version = result.scalar()
        self._connected = True
        self._driver = self._engine.driver
        self._apilevel = self._engine.dialect.dbapi.apilevel
        self._database = self._settings.database
        self._privileges = self._settings.user
        self._publisher = "unknown"

        self.audit(
            caller=self,
            owner=None,
            event=Events.Connected,
            engine=str(self._engine),
            apilevel=str(self._apilevel),
            driver=self._driver,
        )

    def clone(self) -> GenericConnection:
        return PostgresConnection(self._strategy_audit, self._manager, self._settings)

    def operation(self, action: Operation) -> bool:
        if action == Operation.Connect:
            self.connect()
        else:
            self.disconnect()

    def connect(self) -> bool:
        if self._connected:
            return True

        try:
            self._connection = self._engine.connect()
            self._connected = True
            return True
        except Exception:
            return False

    def disconnect(self):
        if not self._connection:
            return
        self._connection = None
        self._engine.dispose()
        self._connected = False

    def settings(self, name):
        return self._settings.get(name)

    def __str__(self) -> str:
        conn = TextStream()
        conn << [
            f"{k}: {v}"
            for k, v in self.__dict__.items()
            if k.lower() not in ["_strategy_audit", "_manager", "password", "framework"]
        ]
        return f"{conn}"
