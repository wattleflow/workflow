# Module name: concrete/workflow.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import difflib
import os
from abc import abstractmethod, ABC
from typing import ClassVar
from logging import getLogger
from wattleflow.core import IConfig, IOriginator
from wattleflow.enums.event import Event
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.manager import (
    ConnectionManager,
    DriverManager,
    ProcessorManager,
)


# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Exceptions                                                           #
# --------------------------------------------------------------------------- #


class WorkflowFactoryException(AuditException):
    pass


# --------------------------------------------------------------------------- #
# endregion Exceptions                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Workflows                                                            #
# --------------------------------------------------------------------------- #


class GenericWorkflow(Wattleflow, IOriginator, ABC):
    __slots__ = (
        "_connections",
        "_drivers",
        "_processors",
        "_level",
        "_handler",
    )

    def __init__(
        self,
        adapter: IConfig,
        connections: ConnectionManager,
        drivers: DriverManager,
        processors: ProcessorManager,
        **kwargs,
    ) -> None:

        super().__init__(**kwargs)
        self.debug(
            msg=Event.Constructor.name,
            step=Event.Started.name,
            connections=connections,
            drivers=drivers,
            processors=processors,
        )

        from wattleflow.concrete.helpers import Attribute

        Attribute.evaluate(self, adapter, IConfig)
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


# --------------------------------------------------------------------------- #
# endregion Workflows                                                         #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region WorkflowFactory                                                      #
# --------------------------------------------------------------------------- #


class WorkflowFactoryLogger(Wattleflow):
    """Standalone audit logger for WorkflowFactory, which is not itself a
    framework object."""


logger = WorkflowFactoryLogger(level="ERROR", logger=getLogger("WorflowFactory"))


class WorkflowFactory:
    _registry: dict[str, type] = {}
    _strategy_defaults: dict[str, str] = {}  # role → fully-qualified class path

    # ------------------------------------------------------------------ #
    # region Registration
    # ------------------------------------------------------------------ #

    @classmethod
    def register(cls, name: str, class_name: type) -> None:
        cls._registry[name] = class_name

    @classmethod
    def resolve(cls, type_name: str) -> type:
        if type_name is None or not isinstance(type_name, str) or not type_name.strip():
            error = (
                f"Missing `type` in config file (got {type_name!r}). "
                "Each connection/driver/processor/pipeline/blackboard/repository "
                "entry must declare a `type:` matching a registered class."
            )
            logger.exception(msg="WorkflowFactory.resolve", name=type_name, error=error)
            raise WorkflowFactoryException(cls, error)

        if type_name not in cls._registry:
            registered = sorted(cls._registry.keys())
            suggestions = difflib.get_close_matches(type_name, registered, n=3, cutoff=0.6)
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            preview = ", ".join(registered[:20]) + (" ..." if len(registered) > 20 else "")
            error = (
                f"Unknown or unregistered type {type_name!r} in config file!"
                f"{hint} Register it via WorkflowFactory.register({type_name!r}, <class>)."
                f" Currently registered ({len(registered)}): [{preview}]"
            )
            logger.exception(
                msg="WorkflowFactory.resolve",
                name=type_name,
                error=error,
                suggestions=suggestions,
                registered_count=len(registered),
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

        # v0.0.0.97 (DR-WFL-012): the caller supplies the configuration source.
        # How it is assembled — file format, secret resolution, .env discovery —
        # belongs to the distribution that owns those parsers, not to the core.
        adapter: IConfig = kwargs.pop("adapter", None)
        if not isinstance(adapter, IConfig):
            raise WorkflowFactoryException(
                cls, f"`adapter` must implement IConfig, got {type(adapter).__name__}."
            )

        # `sections` is the key path of the environment block inside the
        # document (e.g. ("infrastructure", "dev")); every lookup below is
        # resolved under it, so the adapter itself stays unscoped and simple.
        sections = kwargs.pop("sections", None)

        if sections is None:
            raise WorkflowFactoryException(
                cls, "`yaml` must be scoped to a specific path, got None."
            )

        # Workflow class ----------------------------------------------- #
        # Plain config keys: the adapter resolves `<sections>.workflows`, a
        # named list; without a name its single entry is the one to build.
        workflow_name = kwargs.pop("workflow_name", None)
        workflow: dict = adapter.find(*sections, "workflows", default=None)

        if isinstance(workflow, list):
            if workflow_name:
                workflow = next((w for w in workflow if w.get("name") == workflow_name), None)
            elif len(workflow) == 1:
                workflow = workflow[0]

        if not isinstance(workflow, dict):
            raise WorkflowFactoryException(
                cls, f"Workflow {workflow_name!r} not found under `workflows`."
            )

        workflow_class = cls._resolve_section("workflows", workflow)

        # Runtime env vars (e.g. TIKA_SERVER_JAR, JAVA_HOME) ----------- #
        # Applied before connections/drivers/processors are built so any
        # library that reads env at import-time (tika, pyspark) sees them.
        cls._apply_runtime_env(workflow.get("runtime"))

        # Global audit logger settings --------------------------------- #
        global_audit = {
            "level": adapter.find(*sections, "logging", "level", default="NOTSET"),
            "handler": adapter.find(*sections, "logging", "handler", default=None),
            "formating": adapter.find(*sections, "logging", "format", default=None),
        }

        # Worflow Class ------------------------------------------------ #
        connections = cls._build_connections(adapter, sections, **global_audit)
        drivers = cls._build_drivers(adapter, sections, connections, **global_audit)
        processors = cls._build_processors(workflow, drivers, **global_audit)
        return workflow_class(
            adapter=adapter,
            connections=connections,
            drivers=drivers,
            processors=processors,
            **global_audit,
        )

    # ------------------------------------------------------------------ #
    # endregion build
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # region Component builders
    # ------------------------------------------------------------------ #

    # Known runtime keys map to env-vars consumed by external libraries.
    # Anything not in this map is exported verbatim under runtime.env.
    _RUNTIME_KEY_TO_ENV: dict[str, str] = {
        "tika_server_jar": "TIKA_SERVER_JAR",
        "tika_path": "TIKA_PATH",
        "tika_client_only": "TIKA_CLIENT_ONLY",
        "tika_log_path": "TIKA_LOG_PATH",
        "java_home": "JAVA_HOME",
        "spark_home": "SPARK_HOME",
        "pyspark_python": "PYSPARK_PYTHON",
    }

    @classmethod
    def _apply_runtime_env(cls, runtime: dict | None) -> None:
        if not runtime:
            return
        for key, env_name in cls._RUNTIME_KEY_TO_ENV.items():
            value = runtime.get(key)
            if value is None or value == "":
                continue
            os.environ[env_name] = str(value)
            logger.debug(
                msg="WorkflowFactory.runtime",
                key=key,
                env=env_name,
                value=str(value),
            )
        extra = runtime.get("env") or {}
        if isinstance(extra, dict):
            for env_name, value in extra.items():
                if value is None:
                    continue
                os.environ[str(env_name)] = str(value)
                logger.debug(
                    msg="WorkflowFactory.runtime",
                    env=str(env_name),
                    value=str(value),
                )

    # Keys the factory consumes itself: they identify or wire the entry and
    # must never travel on as constructor settings.
    STRUCTURAL: ClassVar[frozenset] = frozenset(
        {
            "name",
            "type",
            "description",
            "configuration",
            "strategy_create",
            "repositories",
            "pipelines",
            "level",
            "handler",
            "formating",
        }
    )

    @classmethod
    def _audit(cls, config: dict, default: dict) -> dict:
        return {
            "level": config.get("level", default["level"]),
            "handler": config.get("handler", default["handler"]),
            "formating": config.get("formating", default["formating"]),
        }

    @classmethod
    def _settings(cls, config: dict) -> dict:
        """Constructor settings for one config entry.

        The documented schema lets a blackboard state its own knobs at its own
        level (`defer_flush:` next to `type:`), with `configuration:` as the
        optional nested form. Reading only the nested form silently dropped the
        documented one — `defer_flush: False` never reached the blackboard, so
        every such workflow ran with the opposite setting. The nested form wins
        on conflict; what the whitelist does not permit PresetDecorator drops.
        """
        nested = config.get("configuration", {}) or {}
        inline = {k: v for k, v in config.items() if k not in cls.STRUCTURAL}
        return {**inline, **nested}

    @classmethod
    def _resolve_section(cls, section: str, item: dict, key: str = "type") -> type:
        """Resolve `item[key]` into a registered class, enriching errors with the
        offending section, item name, and config snippet."""
        try:
            return cls.resolve(item.get(key, None) if isinstance(item, dict) else None)
        except WorkflowFactoryException as e:
            item_name = item.get("name", "<no-name>") if isinstance(item, dict) else "<not-a-dict>"
            error = f"{section}[name={item_name!r}]: {e}"
            logger.exception(
                msg="WorkflowFactory.resolve",
                section=section,
                item_name=item_name,
                error=error,
            )
            raise WorkflowFactoryException(cls, error) from e

    @classmethod
    def _build_connections(
        cls, adapter: IConfig, sections: tuple, **global_audit
    ) -> ConnectionManager:
        manager = ConnectionManager(**global_audit)
        connections = adapter.find(*sections, "managers", "connections", default=[]) or []
        for connection in connections:
            connection_class = cls._resolve_section("managers.connections", connection)
            configuration = connection.get("configuration", {})
            manager.register_connection(
                connection=connection_class(
                    **cls._audit(connection, global_audit),
                    **configuration,
                )
            )

        return manager

    @classmethod
    def _build_drivers(
        cls,
        adapter: IConfig,
        sections: tuple,
        connections: ConnectionManager,
        **global_audit,
    ) -> DriverManager:
        manager = DriverManager(**global_audit)
        drivers = adapter.find(*sections, "managers", "drivers", default=[]) or []
        for driver in drivers:
            driver_class = cls._resolve_section("managers.drivers", driver)
            driver_type = driver.get("type", None)
            driver_name = driver.get("name", driver_type)
            driver_audit = cls._audit(driver, global_audit)
            configuration = dict(driver.get("configuration", {}) or {})

            # Inject ConnectionManager when driver declares a connection_name
            # so connection-backed drivers (Elasticsearch, Postgres, Kafka, ...)
            # can resolve their connection at load time.
            if "connection_name" in configuration:
                configuration.setdefault("connection_manager", connections)

            manager.register_driver(
                driver=driver_class(**configuration, **driver_audit),
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
        if not processors or not isinstance(processors, list):
            raise WorkflowFactoryException(cls, "No processors found in the workflow!")

        for config in processors:
            if not config or isinstance(config, dict) is False:
                raise WorkflowFactoryException(cls, "Configuration is missing for processors")
            # processor class ----------------------------------------------- #
            processor_class = cls._resolve_section("workflows.processors", config)
            proc_audit = cls._audit(config, global_audit)
            configuration = dict(config.get("configuration", {}) or {})

            # Driver may be declared either at processor top-level or inside
            # configuration. Resolve to a registered instance before passing on.
            driver_name = configuration.pop("driver", None) or config.get("driver", None)
            if driver_name:
                configuration["driver"] = drivers.get_driver(driver_name)

            processor = processor_class(**proc_audit, **configuration)

            # pipeline classes ---------------------------------------------- #
            pipelines_config = config.get("pipelines", [])
            for pipeline in pipelines_config:
                pipeline_class = cls._resolve_section("processors.pipelines", pipeline)
                pipeline_audit = cls._audit(pipeline, global_audit)
                pipeline_configuration = dict(pipeline.get("configuration", {}) or {})
                processor.register_pipeline(
                    pipeline=pipeline_class(**pipeline_audit, **pipeline_configuration)
                )

            # Blackboard & strategy_create class ---------------------------- #
            blackboard_config = config.get("blackboard", {}) or {}
            strategy_class = cls._resolve_section(
                "blackboard.strategy_create",
                blackboard_config,
                key="strategy_create",
            )
            logger.debug(msg="_build_processors", strategy=strategy_class)

            # blackboard ------------------------------------------------------
            blackboard_class = cls._resolve_section("processors.blackboard", blackboard_config)
            logger.debug(msg="_build_processors", blackboard=blackboard_class)
            configuration = cls._settings(blackboard_config)
            processor.register_blackboard(
                blackboard=blackboard_class(
                    strategy_create=strategy_class(),
                    **cls._audit(blackboard_config, global_audit),
                    **configuration,
                )
            )

            # repositories ----------------------------------------------------
            repositories = blackboard_config.get("repositories", []) or []
            for repository in repositories:
                audit = cls._audit(repository, global_audit)
                repository_class = cls._resolve_section("blackboard.repositories", repository)
                configuration = repository.get("configuration", {}) or {}
                strategy_write = cls._resolve_section(
                    "blackboard.repositories.strategy_write",
                    configuration,
                    key="strategy_write",
                )
                driver_name = configuration.get("driver", None)
                driver = drivers.get_driver(driver_name) if driver_name else None

                processor.blackboard.register(
                    repository=repository_class(
                        driver=driver,
                        strategy_write=strategy_write(**audit),
                        **audit,
                    )
                )

            configuration = config.get("configuration", {})
            manager.register_processor(
                processor=processor,
                name=config.get("name", processor.name),
                **proc_audit,
                **configuration,
            )

        return manager


__all__ = [
    "GenericWorkflow",
    "WorkflowFactory",
    "WorkflowFactoryException",
    "WorkflowFactoryLogger",
]
