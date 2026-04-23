# Module name: concrete/workflow.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


from __future__ import annotations
from abc import abstractmethod, ABC
from typing import Dict, List, Type
from logging import getLogger
from wattleflow.core import IOriginator
from wattleflow.constants import Event
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.logger import AuditLogger
from wattleflow.concrete.manager import (
    ConnectionManager,
    DriverManager,
    ProcessorManager,
)
from wattleflow.helpers.attribute import Attribute
from wattleflow.helpers.config_adapter import ConfigAdapter


class WorkflowFactoryException(AuditException):
    pass


class GenericWorkflow(IOriginator, AuditLogger, ABC):
    __slots__ = (
        "_connections",
        "_drivers",
        "_processors",
        "_level",
        "_handler",
    )

    def __init__(
        self,
        adapter: ConfigAdapter,
        connections: ConnectionManager,
        drivers: DriverManager,
        processors: ProcessorManager,
    ) -> None:

        level = adapter.find("logging", "level", default="INFO")
        handler = adapter.find("logging", "handler", default=None)
        formating = adapter.find("logging", "format", default=None)
        formating = {"formating": formating} if formating else {}

        AuditLogger.__init__(self, level=level, handler=handler, **formating)
        IOriginator.__init__(self)

        self.debug(
            msg=Event.Constructor.name,
            step=Event.Started.name,
            level=level,
            handler=handler,
            connections=connections,
            drivers=drivers,
            processors=processors,
        )

        Attribute.evaluate(self, adapter, ConfigAdapter)
        Attribute.evaluate(self, connections, ConnectionManager)
        Attribute.evaluate(self, drivers, DriverManager)
        Attribute.evaluate(self, processors, ProcessorManager)

        self._connections: ConnectionManager = connections
        self._drivers: DriverManager = drivers
        self._processors: ProcessorManager = processors

        self.debug(
            msg=Event.Constructor.name,
            step=Event.Completed.name,
            connections=self._connections,
            drivers=self._drivers,
            processor=self._processors,
        )

    def __repr__(self) -> str:
        return f"{self.name}[{self._connections!r}, {self._drivers!r}, {self._processors!r}]"

    @property
    def connections(self) -> ConnectionManager:
        return self._connections

    @property
    def drivers(self) -> DriverManager:
        return self._drivers

    @property
    def processors(self) -> ProcessorManager:
        return self._processors

    @abstractmethod
    def execute(self) -> None: ...


logger = AuditLogger(level="ERROR", logger=getLogger("WorflowFactory"))


class WorkflowFactory:
    _registry: Dict[str, Type] = {}
    _strategy_defaults: Dict[str, str] = {}  # role → fully-qualified class path

    # ------------------------------------------------------------------ #
    # region Registration
    # ------------------------------------------------------------------ #

    @classmethod
    def register(cls, name: str, class_name: Type) -> None:
        cls._registry[name] = class_name

    @classmethod
    def resolve(cls, type_name: str) -> Type:
        if type_name not in cls._registry:
            error = (
                f"Unknown or unregistered `type name` in config file: [{type_name!r}]"
            )
            raise WorkflowFactoryException(cls, error)
        return cls._registry[type_name]

    # ------------------------------------------------------------------ #
    # endregion Registration
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # region Build
    # ------------------------------------------------------------------ #

    @classmethod
    def build(cls, **kwargs) -> GenericWorkflow:
        logger.debug(msg="WorkflowFactory.build", **kwargs)

        config_path = kwargs.pop("config_path")
        workflow_name = kwargs.pop("workflow_name")
        sections = kwargs.pop("sections")

        adapter: ConfigAdapter = ConfigAdapter(config_path, *sections)

        # Workflow class ----------------------------------------------- #
        workflow: List[dict] = adapter.find(
            "workflows",
            name=workflow_name,
            default=None,
        )

        if workflow is None:
            raise ValueError(f"{workflow_name!r} not found in config.workflows.")

        workflow_class = cls.resolve(workflow.get("type", None))

        # Global audit logger settings --------------------------------- #
        global_audit = {
            "level": adapter.find("logging", "level", default="NOTSET"),
            "handler": adapter.find("logging", "handler", default=None),
            "formating": adapter.find("logging", "format", default=None),
        }

        # Worflow Class ------------------------------------------------ #
        connections = cls._build_connections(adapter, **global_audit)
        drivers = cls._build_drivers(adapter, **global_audit)
        processors = cls._build_processors(workflow, drivers, **global_audit)
        return workflow_class(
            adapter=adapter,
            connections=connections,
            drivers=drivers,
            processors=processors,
        )

    # ------------------------------------------------------------------ #
    # endregion build
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # region Component builders
    # ------------------------------------------------------------------ #

    @classmethod
    def _audit(cls, config: dict, default: dict) -> dict:
        return {
            "level": config.get("level", default["level"]),
            "handler": config.get("handler", default["handler"]),
            "formating": config.get("formating", default["formating"]),
        }

    @classmethod
    def _build_connections(
        cls, adapter: ConfigAdapter, **global_audit
    ) -> DriverManager:
        manager = ConnectionManager(**global_audit)
        connections = adapter.find("managers", "connections", default=[])
        for connection in connections:
            connection_class = cls.resolve(connection.get("type", None))
            configuration = connection.get("configuration", {})
            manager.register_connection(
                connection=connection_class(
                    **cls._audit(connection, global_audit),
                    **configuration,
                )
            )

        return manager

    @classmethod
    def _build_drivers(cls, adapter: ConfigAdapter, **global_audit) -> DriverManager:
        manager = DriverManager(**global_audit)
        drivers = adapter.find("managers", "drivers", default=[])
        for driver in drivers:
            driver_type = driver.get("type", None)
            driver_class = cls.resolve(driver_type)
            driver_name = driver.get("name", driver_type)
            driver_audit = cls._audit(driver, global_audit)
            manager.register_driver(
                driver=driver_class(**driver.get("configuration", {}), **driver_audit),
                name=driver_name,
                **driver_audit,
            )

        return manager

    @classmethod
    def _build_processors(
        cls, workflow: dict, drivers: DriverManager, **global_audit
    ) -> ProcessorManager:
        manager = ProcessorManager(**global_audit)

        # Processors config ------------------------------------------------- #
        processors = workflow.get("processors", [])

        for config in processors:
            # processor class ----------------------------------------------- #
            processor_class = cls.resolve(config.get("type"))
            proc_audit = cls._audit(config, global_audit)
            processor = processor_class(**proc_audit, **config.get("configuration", {}))

            # pipeline classes ---------------------------------------------- #
            pipelines_config = config.get("pipelines", [])
            for pipeline in pipelines_config:
                pipeline_class = cls.resolve(pipeline.get("type", None))
                pipeline_audit = cls._audit(pipeline, global_audit)
                processor.register_pipeline(pipeline=pipeline_class(**pipeline_audit))

            # Blackboard & strategy_create class ---------------------------- #
            strategy_class = cls.resolve(
                config.get("blackboard", {}).get("strategy_create", None)
            )
            logger.debug(msg="_build_processors", strategy=strategy_class)

            # blackboard ------------------------------------------------------
            blackboard_config = config.get("blackboard", {})
            blackboard_class = cls.resolve(blackboard_config.get("type", None))
            logger.debug(msg="_build_processors", blackboard=blackboard_class)
            configuration = blackboard_config.get("configuration", {})
            processor.register_blackboard(
                blackboard=blackboard_class(
                    strategy_create=strategy_class(),
                    **cls._audit(blackboard_config, global_audit),
                    **configuration,
                )
            )

            # repositories ----------------------------------------------------
            repositories = blackboard_config.get("repositories", {})
            for repository in repositories:
                audit = cls._audit(repository, global_audit)
                repository_class = cls.resolve(repository.get("type", None))
                configuration = repository.get("configuration", None)
                # strategy_read = cls.resolve(configuration.get("strategy_read", None))
                strategy_write = cls.resolve(configuration.get("strategy_write", None))
                driver = drivers.get_driver(name=configuration.get("driver", None))

                processor.blackboard.register(
                    repository=repository_class(
                        driver=driver,
                        # strategy_read=strategy_read(**audit),
                        strategy_write=strategy_write(**audit),
                        **audit,
                    )
                )

            configuration = config.get("configuration", {})
            manager.register_processor(
                processor=processor,
                name=config.get("type", processor.name),
                **proc_audit,
                **configuration,
            )

        return manager

    # ------------------------------------------------------------------ #
    # endregion Component builders
    # ------------------------------------------------------------------ #
    # Helpers

    # @classmethod
    # def _load_strategy(cls, path: Optional[str], role: str) -> Optional[Any]:
    #     target = path or cls._strategy_defaults.get(role)
    #     if target:
    #         return ClassLoader(class_path=target).instance
    #     return None
