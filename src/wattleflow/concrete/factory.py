# Module name: concrete/factory.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations

__all__ = [
    "WorkflowFactory",
    "WorkflowFactoryException",
]

import difflib
import os
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, ClassVar, NoReturn
from logging import getLogger
from wattleflow.core import IConfig
from wattleflow.enums.event import Event
from wattleflow.concrete.exception import AuditException
from wattleflow.concrete.memento_store import (
    FileMementoStore,
    MementoStore,
    MementoStoreException,
    MemoryMementoStore,
)
from wattleflow.helpers.audit import Audit
from wattleflow.helpers.moment import MomentHelper
from wattleflow.helpers.monitor import Monitor, MonitorLevel
from wattleflow.helpers.resources import ResourceManager
from wattleflow.concrete.base import Wattleflow
from wattleflow.concrete.manager import (
    ConnectionManager,
    DriverManager,
    ManagerException,
    ProcessorManager,
)
from wattleflow.decorators.preset import PresetGate

if TYPE_CHECKING:
    from wattleflow.concrete.workflow import GenericWorkflow


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
# region Factory                                                              #
# --------------------------------------------------------------------------- #


class WorkflowFactoryLogger(Wattleflow):
    """Standalone audit logger for WorkflowFactory, not framework object."""

    __slots__ = ()
    # ERROR until a workflow is built: before the YAML is read there is no declared
    # level to honour, and a library that talks on import is a nuisance. `build()`
    # raises it to the workflow's own level as soon as it knows one.


logger = WorkflowFactoryLogger(level="ERROR", logger=getLogger("WorkflowFactory"))


class WorkflowFactory:
    # Class-level registry only: the factory is never instantiated, so it has no
    # per-instance slots (a slot named like a class variable is a ValueError).
    __slots__ = ()

    _registry: dict[str, type] = {}

    # ------------------------------------------------------------------ #
    # region Registration
    # ------------------------------------------------------------------ #

    @classmethod
    def register(cls, name: str, class_name: type) -> None:
        if not isinstance(class_name, type):
            raise WorkflowFactoryException(
                cls, f"Only a class can be registered; {name!r} got {type(class_name).__name__}."
            )
        known = cls._registry.get(name)
        if known is not None and known is not class_name:
            # A name taken by another class is a decision somebody should see.
            logger.warning(
                msg=Event.Register,
                name=name,
                replaced=known.__qualname__,
                by=class_name.__qualname__,
            )
        cls._registry[name] = class_name

    @classmethod
    def resolve(cls, type_name: str) -> type:
        if type_name is None or not isinstance(type_name, str) or not type_name.strip():
            error = (
                f"Missing `type` in config file (got {type_name!r}). "
                "Each connection/driver/processor/pipeline/blackboard/repository "
                "entry must declare a `type:` matching a registered class."
            )
            logger.exception(msg=Event.Resolve, name=type_name, error=error)
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
                msg=Event.Resolve,
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
        logger.debug(msg=Event.Build, **kwargs)
        adapter: IConfig = kwargs.pop("adapter", None)
        if not isinstance(adapter, IConfig):
            raise WorkflowFactoryException(
                cls, f"`adapter` must implement IConfig, got {type(adapter).__name__}."
            )

        sections = kwargs.pop("sections", None)

        # Optional hook: called with a component class, returns the extra keywords for its
        # constructor ({} for none). The factory does not know what they are (BR-OSCAL-21).
        component_kwargs = kwargs.pop("component_kwargs", None)

        if sections is None:
            raise WorkflowFactoryException(
                cls, "`yaml` must be scoped to a specific path, got None."
            )

        # Workflow class ----------------------------------------------- #
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
        cls._report_inline("workflows", workflow, {"processors", "runtime", "memento"})

        cls._apply_runtime_env(workflow.get("runtime"))
        MomentHelper.configure()

        declared_level = adapter.find(*sections, "logging", "level", default=None)
        if declared_level is not None:
            resolved = Audit.resolve_level(declared_level)
            getLogger().setLevel(resolved)

            logger.set_level(resolved)

        if declared_level is None:
            logger.set_level(getLogger().getEffectiveLevel())

        global_audit = {
            "handler": adapter.find(*sections, "logging", "handler", default=None),
            "formatting": adapter.find(*sections, "logging", "format", default=None),
        }

        connections = cls._build_connections(adapter, sections, component_kwargs, **global_audit)
        drivers = cls._build_drivers(
            adapter, sections, connections, component_kwargs, **global_audit
        )
        processors = cls._build_processors(workflow, drivers, component_kwargs, **global_audit)
        logger.info(
            msg=Event.Build,
            step=Event.Completed,
            connections=len(connections),
            drivers=len(drivers),
            processors=len(processors),
        )
        built = workflow_class(
            adapter=adapter,
            connections=connections,
            drivers=drivers,
            processors=processors,
            **cls._audit(workflow, global_audit),
        )
        cls._configure_monitor(adapter, sections, built, workflow)
        return built

    # Stores a `memento:` section can name without registering anything.
    _MEMENTO_STORES: ClassVar[dict[str, type]] = {
        "memory": MemoryMementoStore,
        "file": FileMementoStore,
    }

    @classmethod
    def _build_memento(cls, workflow: dict) -> tuple[MementoStore | None, int | None]:
        """`memento:` on the workflow entry switches checkpointing on for its processors.

        `store:` is `memory`, `file` or a registered MementoStore; `path:` is the directory a
        file store keeps its snapshots in (the same path after a restart is what resumes a
        run); `checkpoint_every:` is the cycle interval. Without the section: no store.
        """
        section = workflow.get("memento")
        if section is None:
            return None, None
        if not isinstance(section, dict):
            cls._fail("workflows.memento", workflow, "`memento` must be a mapping")
        name = section.get("store")
        store_class = cls._MEMENTO_STORES.get(name) if isinstance(name, str) else None
        if store_class is None:
            store_class = cls._resolve_section("workflows.memento", section, key="store")
        if not (isinstance(store_class, type) and issubclass(store_class, MementoStore)):
            cls._fail("workflows.memento", workflow, f"{name!r} is not a MementoStore")
        options = {k: v for k, v in section.items() if k not in ("store", "checkpoint_every")}
        try:
            store = store_class(**options)
        except Exception as error:
            cls._fail("workflows.memento", workflow, str(error), cause=error)
        return store, section.get("checkpoint_every")

    @classmethod
    def _build_exporters(
        cls, exporters: Any, built: GenericWorkflow, workflow_name: str | None = None
    ) -> list:
        """`monitoring: exporters:` — `sink:` a registered sink class, `driver:` a driver
        under `managers.drivers`; the rest are the sink's own keywords. An exporter that
        names no `instance` is grouped under the workflow's name."""
        sinks = []
        for entry in exporters or ():
            if not isinstance(entry, dict) or "sink" not in entry:
                cls._fail("monitoring.exporters", entry, "each exporter needs `sink:`")
            options = dict(entry)
            if workflow_name and "instance" not in options:
                options["instance"] = workflow_name
            sink_class = cls.resolve(options.pop("sink"))
            driver_name = options.pop("driver", None)
            driver = built.drivers.get_driver(driver_name) if driver_name else None
            sinks.append(sink_class(driver=driver, **options))
        return sinks

    @classmethod
    def _configure_monitor(
        cls,
        adapter: IConfig,
        sections: tuple,
        built: GenericWorkflow,
        workflow: dict | None = None,
    ) -> None:
        """v0.0.1.14 (FRQ-PTN-18.1 EV01): level, thresholds, extensions and limits at build.
        Without a `monitoring:` section, or with `level: OFF`, no monitor exists at all."""
        monitoring = adapter.find(*sections, "monitoring", default=None) or {}
        if not isinstance(monitoring, dict):
            cls._fail("monitoring", monitoring, "must be a mapping")
        unknown = sorted(set(monitoring) - cls._MONITORING_KEYS)
        if unknown:
            logger.warning(msg=Event.Configure, target="monitoring", discarded=unknown)
        level = MonitorLevel.resolve(monitoring.get("level", "OFF"))
        if level == MonitorLevel.OFF:
            return
        workflow_name = (workflow or {}).get("name")
        # never accept (FRQ-PTN-18.1 §11 t.3).
        manager = ResourceManager(
            limits=monitoring.get("limits"),
            thresholds=monitoring.get("thresholds"),
            extensions=[cls.resolve(name)() for name in monitoring.get("extensions") or ()],
        )
        monitor = Monitor()
        monitor.configure(
            level=level,
            roles=monitoring.get("roles"),
            thresholds=monitoring.get("thresholds"),
            interval=monitoring.get("interval"),
            sinks=cls._build_exporters(monitoring.get("exporters"), built, workflow_name),
            labels={
                "workflow": workflow_name,
                "app": adapter.find("app", "name", default=None),
            },
            limits=manager,
        )
        manager.announce(built.measured_paths())
        built.attach_monitor(monitor)

    # ------------------------------------------------------------------ #
    # endregion build
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # region Component builders
    # ------------------------------------------------------------------ #

    # Known runtime keys map to env-vars consumed by external libraries.
    # Anything not in this map is exported verbatim under runtime.env.
    _MONITORING_KEYS: frozenset[str] = frozenset(
        {
            "level",
            "roles",
            "thresholds",
            "extensions",
            "interval",
            "exporters",
            "limits",
        }
    )

    _RUNTIME_KEY_TO_ENV: dict[str, str] = {
        "tika_server_jar": "TIKA_SERVER_JAR",
        "tika_path": "TIKA_PATH",
        "tika_client_only": "TIKA_CLIENT_ONLY",
        "tika_log_path": "TIKA_LOG_PATH",
        "java_home": "JAVA_HOME",
        "spark_home": "SPARK_HOME",
        "pyspark_python": "PYSPARK_PYTHON",
        "time_zone": "WATTLEFLOW_TIME_ZONE",
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
            # The known keys are installation paths; the value is part of the trace.
            logger.debug(
                msg=Event.Configure,
                stage="runtime",
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
                    msg=Event.Configure,
                    stage="runtime",
                    env=str(env_name),
                    value="<set>",
                )

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
            "formatting",
        }
    )

    AUDIT_KEYS: ClassVar[frozenset] = frozenset({"level", "handler", "formatting"})

    @classmethod
    def _audit(cls, config: dict, default: dict) -> dict:
        """Audit settings for one YAML entry: its own, else the workflow's.

        `level` is deliberately absent unless THIS entry declares one — the
        workflow default lives on the root logger and is inherited. Any entry
        (driver, processor, pipeline, blackboard, repository) may declare
        `level:` beside its `name`/`type` OR inside its `configuration:`; both
        read the same, because both are how the setting is written in practice.
        It applies to the entry's CLASS, which is the granularity a per-class
        logger can carry.
        """
        nested = config.get("configuration") or {}
        audit = {
            "handler": config.get("handler", nested.get("handler", default["handler"])),
            "formatting": config.get(
                "formatting", nested.get("formatting", default["formatting"])
            ),
        }
        level = config.get("level", nested.get("level"))
        if level is not None:
            audit["level"] = level
        return audit

    @classmethod
    def _report_inline(cls, section: str, item: dict, extra: Iterable[str] = ()) -> None:
        """A key an entry carries that the factory neither consumes nor passes on would vanish
        unseen: say so, with the section, the entry and the keys. (Only the blackboard merges
        inline keys into its settings; everywhere else they belong in `configuration:`.)"""
        if not isinstance(item, dict):
            return
        unknown = sorted(str(k) for k in item if k not in cls.STRUCTURAL and k not in extra)
        if unknown:
            logger.warning(
                msg=Event.Configure,
                section=section,
                name=item.get("name", "<no-name>"),
                discarded=unknown,
                hint="put it under `configuration:`",
            )

    @classmethod
    def _configuration(cls, config: dict) -> dict:
        """An entry's constructor settings, with the audit keys removed."""
        return {
            key: value
            for key, value in (config.get("configuration") or {}).items()
            if key not in cls.AUDIT_KEYS
        }

    @classmethod
    def _settings(cls, config: dict) -> dict:
        nested = cls._configuration(config)
        inline = {k: v for k, v in config.items() if k not in cls.STRUCTURAL}
        return {**inline, **nested}

    @classmethod
    def _fail(
        cls, section: str, item: dict, error: str, cause: Exception | None = None
    ) -> NoReturn:
        """Report a configuration failure with the offending section and item name."""
        item_name = item.get("name", "<no-name>") if isinstance(item, dict) else "<not-a-dict>"
        reason = f"{section}[name={item_name!r}]: {error}"

        # `exception()` forces exc_info; without a cause it would log "NoneType: None".
        report = logger.exception if cause is not None else logger.error
        report(
            msg=Event.Resolve,
            section=section,
            item_name=item_name,
            error=reason,
        )
        raise WorkflowFactoryException(cls, reason) from cause

    @classmethod
    def _resolve_section(cls, section: str, item: dict, key: str = "type") -> type:
        """Resolve `item[key]` into a registered class."""
        try:
            return cls.resolve(item.get(key, None) if isinstance(item, dict) else None)
        except WorkflowFactoryException as e:
            cls._fail(section, item, str(e), cause=e)

    @classmethod
    def _driver_context(
        cls,
        section: str,
        item: dict,
        target: type,
        configuration: dict,
        drivers: DriverManager,
    ) -> dict:
        """Keywords carrying the driver a component declared that it takes.

        The requirement is read from the class's own preset declaration, so the
        factory stays agnostic of concrete component types.
        """
        if "driver" not in PresetGate.resolve(target):
            return {}

        name = configuration.get("driver", None)
        if not name:
            cls._fail(
                section,
                item,
                f"configuration.driver is mandatory for {target.__name__}",
            )

        try:
            return {"driver": drivers.get_driver(name)}
        except ManagerException as e:
            cls._fail(
                section,
                item,
                f"driver {name!r} is not registered under managers.drivers",
                cause=e,
            )

    @classmethod
    def _extra(cls, hook, component: type) -> dict:
        """Keywords the `component_kwargs` hook adds for this class; none without a hook."""
        return {} if hook is None else dict(hook(component))

    @classmethod
    def _build_connections(
        cls, adapter: IConfig, sections: tuple, component_kwargs=None, **global_audit
    ) -> ConnectionManager:
        manager = ConnectionManager(**global_audit)
        connections = adapter.find(*sections, "managers", "connections", default=[]) or []
        for connection in connections:
            connection_class = cls._resolve_section("managers.connections", connection)
            cls._report_inline("managers.connections", connection)
            configuration = cls._configuration(connection)
            manager.register_connection(
                connection=connection_class(
                    **cls._audit(connection, global_audit),
                    **configuration,
                    **cls._extra(component_kwargs, connection_class),
                )
            )

        return manager

    @classmethod
    def _build_drivers(
        cls,
        adapter: IConfig,
        sections: tuple,
        connections: ConnectionManager,
        component_kwargs=None,
        **global_audit,
    ) -> DriverManager:
        manager = DriverManager(**global_audit)
        drivers = adapter.find(*sections, "managers", "drivers", default=[]) or []
        for driver in drivers:
            driver_class = cls._resolve_section("managers.drivers", driver)
            cls._report_inline("managers.drivers", driver)
            driver_type = driver.get("type", None)
            driver_name = driver.get("name", driver_type)
            driver_audit = cls._audit(driver, global_audit)
            configuration = cls._configuration(driver)

            # Inject ConnectionManager when driver declares a connection_name
            # so connection-backed drivers (Elasticsearch, Postgres, Kafka, ...)
            # can resolve their connection at load time.
            if "connection_name" in configuration:
                configuration.setdefault("connection_manager", connections)

            manager.register_driver(
                driver=driver_class(
                    **configuration, **driver_audit, **cls._extra(component_kwargs, driver_class)
                ),
                name=driver_name,
                **driver_audit,
            )

        return manager

    @classmethod
    def _build_processors(
        cls, workflow: dict, drivers: DriverManager, component_kwargs=None, **global_audit
    ) -> ProcessorManager:
        manager = ProcessorManager(**global_audit)
        memento_store, checkpoint_every = cls._build_memento(workflow)

        # Processors config ------------------------------------------------- #
        processors = workflow.get("processors", [])
        if not processors or not isinstance(processors, list):
            raise WorkflowFactoryException(cls, "No processors found in the workflow!")

        for config in processors:
            if not config or isinstance(config, dict) is False:
                raise WorkflowFactoryException(cls, "Configuration is missing for processors")
            # processor class ----------------------------------------------- #
            processor_class = cls._resolve_section("workflows.processors", config)
            cls._report_inline("workflows.processors", config, {"driver", "blackboard"})
            proc_audit = cls._audit(config, global_audit)
            configuration = cls._configuration(config)

            # Driver may be declared either at processor top-level or inside
            # configuration. Resolve to a registered instance before passing on.
            driver_name = configuration.pop("driver", None) or config.get("driver", None)
            if driver_name:
                try:
                    configuration["driver"] = drivers.get_driver(driver_name)
                except ManagerException as e:
                    cls._fail(
                        "workflows.processors",
                        config,
                        f"driver {driver_name!r} is not registered under managers.drivers",
                        cause=e,
                    )

            if memento_store is not None:
                # The registered name is the checkpoint's key: it is what a restart finds again.
                key = config.get("name") or processor_class.__name__
                try:
                    MementoStore._check_key(key)
                except MementoStoreException as error:
                    cls._fail("workflows.processors", config, str(error), cause=error)
                configuration.setdefault("memento_store", memento_store)
                configuration.setdefault("memento_key", key)
                if checkpoint_every is not None:
                    configuration.setdefault("checkpoint_every", checkpoint_every)

            processor = processor_class(
                **proc_audit, **configuration, **cls._extra(component_kwargs, processor_class)
            )

            # pipeline classes ---------------------------------------------- #
            pipelines_config = config.get("pipelines", [])
            for pipeline in pipelines_config:
                pipeline_class = cls._resolve_section("processors.pipelines", pipeline)
                cls._report_inline("processors.pipelines", pipeline)
                pipeline_audit = cls._audit(pipeline, global_audit)
                pipeline_configuration = cls._configuration(pipeline)
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
            logger.debug(msg=Event.Build, target="processors", strategy=strategy_class)

            # blackboard ------------------------------------------------------
            blackboard_class = cls._resolve_section("processors.blackboard", blackboard_config)
            logger.debug(msg=Event.Build, target="processors", blackboard=blackboard_class)
            configuration = cls._settings(blackboard_config)
            blackboard_audit = cls._audit(blackboard_config, global_audit)
            processor.register_blackboard(
                blackboard=blackboard_class(
                    # The create strategy has no entry of its own in the YAML —
                    # it is named as a string on the blackboard — so the
                    # blackboard's audit settings are the ones it can inherit.
                    # Built bare, it could not be configured at all.
                    strategy_create=strategy_class(**blackboard_audit),
                    **blackboard_audit,
                    **configuration,
                )
            )

            # repositories ----------------------------------------------------
            repositories = blackboard_config.get("repositories", []) or []
            for repository in repositories:
                audit = cls._audit(repository, global_audit)
                repository_class = cls._resolve_section("blackboard.repositories", repository)
                cls._report_inline("blackboard.repositories", repository)
                configuration = repository.get("configuration", {}) or {}
                options = {
                    key: value
                    for key, value in configuration.items()
                    if key not in ("driver", "strategy_read", "strategy_write")
                }
                strategy_write = cls._resolve_section(
                    "blackboard.repositories.strategy_write",
                    configuration,
                    key="strategy_write",
                )
                # Optional: a repository that is only written to declares none.
                strategy_read = None
                if configuration.get("strategy_read"):
                    strategy_read = cls._resolve_section(
                        "blackboard.repositories.strategy_read",
                        configuration,
                        key="strategy_read",
                    )(**audit, **options)
                driver = cls._driver_context(
                    "blackboard.repositories",
                    repository,
                    repository_class,
                    configuration,
                    drivers,
                )

                processor.blackboard.register(
                    repository=repository_class(
                        **driver,
                        strategy_write=strategy_write(**audit, **options),
                        strategy_read=strategy_read,
                        **audit,
                    )
                )

            configuration = cls._configuration(config)
            manager.register_processor(
                processor=processor,
                name=config.get("name", processor.name),
                **proc_audit,
                **configuration,
            )

        return manager


# --------------------------------------------------------------------------- #
# endregion Factory                                                           #
# --------------------------------------------------------------------------- #
