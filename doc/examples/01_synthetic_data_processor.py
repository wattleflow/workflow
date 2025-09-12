# Module Name: 01_processor_synthetic_data.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence
# Description:
#   This module demonstrates a simple tests that generate synthetic data
#   using Workflow framework with simple processors and pipelines.

import gc
import logging
import os
import pandas as pd

from faker import Faker
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from wattleflow.core import (
    IBlackboard,
    ICommand,
    IPipeline,
    IProcessor,
    IRepository,
    ITarget,
    IWattleflow,
)
from wattleflow.concrete import (
    AuditLogger,
    DocumentFacade,
    GenericProcessor,
    GenericBlackboard,
    GenericRepository,
    GenericPipeline,
    StrategyCreate,
    StrategyRead,
    StrategyWrite,
)
from wattleflow.constants import Event
from wattleflow.documents import DataFrameDocument, DictDocument
from wattleflow.helpers import Attribute, Config, Project


_empty = lambda n: [" " for _ in range(1, n)]
_specific = lambda s, n: [s for _ in range(1, n)]
_date = lambda f, n: [f.date_this_year() for _ in range(1, n)]
_name = lambda f, n: [f.name() for _ in range(1, n)]
_sentence = lambda f, n: [f.sentence(nb_words=5) for _ in range(1, n)]
_email = lambda f, n: [
    "<{}>, <{}>, <{}>".format(f.email(), f.email(), f.email()) for _ in range(1, n)
]


# --------------------------------------------------------------------------- #
# IMPORTANT:
# This test case requires the faker library.
# Ensure you have it installed using: pip install faker
# The library is used to generate fake data and dataframes for manipulation.
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #


# Mockup
class StrategyCreateSimpleMock(StrategyCreate):
    def execute(self, caller: IWattleflow, *args, **kwargs) -> Optional[ITarget]:
        self.debug(
            msg=Event.Created.value,
            caller=caller,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=caller, expected_type=IProcessor)

        content = {
            "order": kwargs.pop("order", 0),
            "sql": kwargs.pop("sql", "missing"),
            "publisher": kwargs.pop("publisher", "unknown"),
            "connection": kwargs.pop("mock_connection", "unknown"),
        }

        return DocumentFacade(DictDocument(content=content))


class StrategyReadSimpleMock(StrategyRead):
    def execute(
        self,
        caller: IWattleflow,
        identifier: str,
        *args,
        **kwargs,
    ) -> Optional[ITarget]:

        self.debug(
            msg=Event.Executing.value,
            caller=caller.name,
            identifier=identifier,
            *args,
            **kwargs,
        )

        Attribute.mandatory(caller=self, name="identifier", cls=str, kwargs=kwargs)
        Attribute.mandatory(caller=self, name="repository", cls=IRepository, **kwargs)

        raise NotImplementedError("Not used.")


class StrategyWriteSimpleMock(StrategyWrite):
    def execute(self, caller: IWattleflow, document: ITarget, *args, **kwargs) -> bool:
        self.debug(
            msg=Event.Executing.value,
            caller=caller.name,
            document=document,
            *args,
            **kwargs,
        )
        return True


# DataFrame
class StrategyCreateDataFrame(StrategyCreate):
    def execute(self, caller: IWattleflow, *args, **kwargs) -> Optional[ITarget]:
        self.debug(msg=Event.Created.value, caller=caller, name=repr(caller))

        Attribute.mandatory(caller=self, name="data", cls=pd.DataFrame, **kwargs)
        Attribute.evaluate(caller=self, target=caller, expected_type=IProcessor)

        self.debug(
            msg=Event.Created.value,
            processor=repr(caller),
            size=len(self.data),  # type: ignore
        )

        if self.data.empty:  # type: ignore
            self.warning(msg=Event.Creating.value, fnc="execute: empty dataframe")
            return
        return DocumentFacade(DataFrameDocument(content=self.data))


class StrategyWriteDataFrame(StrategyWrite):
    def execute(self, caller: IWattleflow, document: ITarget, *args, **kwargs) -> bool:
        self.debug(
            msg=Event.ProcessingTask.value,
            caller=caller,
            document=document,
            **kwargs,
        )

        Attribute.evaluate(caller=self, target=caller, expected_type=IPipeline)
        Attribute.mandatory(caller=self, name="repository", cls=IRepository, **kwargs)
        Attribute.mandatory(caller=self, name="processor", cls=IProcessor, **kwargs)

        storage_path = self.repository.storage_path  # type: ignore

        file_path = self.processor.name.lower()  # type: ignore
        file_path = os.path.join(storage_path, file_path)

        if not os.path.exists(file_path):
            os.makedirs(file_path)

        document_adaptee: DataFrameDocument = document.request()  # type: ignore

        Attribute.evaluate(
            caller=self,
            target=document_adaptee.content,
            expected_type=pd.DataFrame,
        )

        if document_adaptee.content.empty:  # type: ignore
            self.warning(
                msg=Event.Executing.value,
                id=document_adaptee.identifier,
                size=document_adaptee.size,
                reason="Empty data frame!",
            )
            return False

        filename = "{}.csv".format(os.path.join(file_path, document_adaptee.identifier))

        document_adaptee.content.to_csv(filename, index=False, header=True)  # type: ignore

        self.info(
            msg=Event.Stored.value,
            filename=filename,
            size=len(document_adaptee.content),  # type: ignore
        )

        return True


class StrategyWriteFileDocument(StrategyWrite):
    def execute(self, caller: IWattleflow, document: ITarget, *args, **kwargs) -> bool:
        self.debug(
            msg=Event.ProcessingTask.value,
            caller=caller,
            document=document,
            **kwargs,
        )

        Attribute.mandatory(caller=self, name="repository", cls=IRepository, **kwargs)
        Attribute.mandatory(caller=self, name="pipeline", cls=IPipeline, **kwargs)

        storage_path: Path = Path(self.repository.storage_path)  # type: ignore

        if not storage_path.exists():
            storage_path.mkdir(parents=True)
            self.debug(msg=Event.Created.value, storage_path=str(storage_path.absolute))

        doc: DataFrameDocument = document.request()  # type: ignore
        Attribute.evaluate(caller=self, target=doc, expected_type=DataFrameDocument)

        if doc.size <= 0:
            self.warning(
                msg=Event.Executing.value,
                id=doc.identifier,
                size=doc.size,
                reason="empty document",
            )
            return False

        data_frame: pd.DataFrame = doc.specific_request()  # type: ignore
        Attribute.evaluate(caller=self, target=data_frame, expected_type=pd.DataFrame)

        if data_frame.empty:  # type: ignore
            self.warning(
                msg=Event.Writing.value,
                caller=self.name,
                reason="empty dataframe",
            )

        pipeline_name = self.pipeline.name.lower()  # type: ignore
        pipeline_path = os.path.join(str(storage_path.absolute), pipeline_name)
        file_path = "{}.csv".format(os.path.join(pipeline_path, doc.identifier))
        data_frame.to_csv(file_path, index=False, header=True)

        self.info(
            msg=Event.Stored.value,
            filename=file_path,
            pipeline=pipeline_name,
        )

        return True


# --------------------------------------------------------------------------- #
# Pipelines
# --------------------------------------------------------------------------- #


class PipelineTest(GenericPipeline):
    """Simple test to show pipeline functionality"""

    def process(
        self,
        processor: IProcessor,
        document: ITarget,
        *args,
        **kwargs,
    ) -> None:
        super().process(processor=processor, document=document, **kwargs)

        uid: str = processor.blackboard.write(  # type: ignore
            document=document,
            caller=self,
            **kwargs,
        )

        self.debug(
            msg=Event.TaskCompleted.value,
            uid=uid,
            processor=processor.name,
            document=document,
        )


class PipelineSyntheticData(GenericPipeline):
    """
    Generates synthetic data simulating `dirty` records using empty and incorrect id's.
    The data is generated using Faker, and then combined in one dataframe before updating
    document and stored via Blackboard.
    """

    def process(
        self,
        processor: IProcessor,
        document: ITarget,
        *args,
        **kwargs,
    ) -> None:
        super().process(processor=processor, document=document, *args, **kwargs)

        ff = Faker()
        document_adaptee: DataFrameDocument = document.request()  # type: ignore

        wrong_ids = {
            "ID": ["AE{}".format(ff.random_number(digits=7)) for n in range(1, 5)],
            "Created": _date(ff, 5),
            "Created by": _name(ff, 5),
            "Description": _sentence(ff, 5),
            "Email": _email(ff, 5),
        }

        data = pd.concat([document_adaptee.content, pd.DataFrame(wrong_ids)], axis=0)

        empty_ids = {
            "ID": _empty(5),
            "Created": _date(ff, 5),
            "Created by": _name(ff, 5),
            "Description": _sentence(ff, 5),
            "Email": _email(ff, 5),
        }

        data = pd.concat([data, pd.DataFrame(empty_ids)], axis=0)

        dirty_records = {
            "ID": _specific("123456789", 5),
            "Created": _date(ff, 5),
            "Created by": _name(ff, 5),
            "Description": _sentence(ff, 5),
            "Email": _email(ff, 5),
        }

        data_frame = pd.concat([data, pd.DataFrame(dirty_records)], axis=0)
        document_adaptee.update_content(data_frame)

        processor.blackboard.write(  # type: ignore
            caller=self,
            document=document,
            processor=processor,
        )

        self.debug(
            msg=Event.TaskCompleted.value,
            content=type(data_frame).__name__,
            records=len(data_frame),
        )


class PipelineCleanupData(GenericPipeline):
    """
    This pipeline simulates data claning, by converting ID's to integers
    and dropping incorrect or null values and stores them via Blackboard.
    """

    def process(
        self,
        processor: IProcessor,
        document: ITarget,
        *args,
        **kwargs,
    ) -> None:

        super().process(processor=processor, document=document, *args, **kwargs)

        document_adaptee: DataFrameDocument = document.request()  # type: ignore
        Attribute.evaluate(
            caller=self,
            target=document_adaptee,
            expected_type=DataFrameDocument,
        )

        self.debug(
            msg=Event.ProcessingTask.value,
            id=document_adaptee.identifier,
            content=type(document_adaptee.content),
            size=document_adaptee.size,
        )

        data_frame: pd.DataFrame = document_adaptee.content  # type: ignore

        Attribute.evaluate(
            caller=self,
            target=document_adaptee.content,
            expected_type=pd.DataFrame,
        )

        data_frame = data_frame[
            pd.to_numeric(data_frame["ID"], errors="coerce").notnull()
        ]

        # data = data[pd.to_numeric(data["ID"], downcast="integer").notnull()]
        data_frame.loc[:, "ID"] = data_frame["ID"].astype(int)
        document_adaptee.update_content(data_frame)

        identifier: str = processor.blackboard.write(  # type: ignore
            caller=self,
            document=document,
            processor=processor,
        )

        self.debug(
            msg=Event.TaskCompleted.value,
            identifier=identifier,
            document=document,
            status="stored",
        )


class PipelineFilterQuery(GenericPipeline):
    """
    This pipeline uses query to filter specific emails from the dataframe
    and stores them via Blackboard.
    """

    def process(
        self,
        processor: IProcessor,
        document: ITarget,
        *args,
        **kwargs,
    ) -> None:

        super().process(processor=processor, document=document, *args, **kwargs)

        document_adaptee: DataFrameDocument = document.request()  # type: ignore
        data_frame: pd.DataFrame = document_adaptee.content  # type: ignore
        Attribute.evaluate(caller=self, target=data_frame, expected_type=pd.DataFrame)

        # list used in query
        id_list = [123456789, 1000000]  # noqa: F841 - used in query string
        allowed_emails = ["example.org", "example.net"]
        pattern = "|".join(allowed_emails)  # noqa: F841 - used in query string

        found = data_frame.query(
            "ID in @id_list and Email.str.contains(@pattern)",
            engine="python",
        )

        document_adaptee.update_content(found)
        uid = processor.blackboard.write(  # type: ignore
            caller=self,
            document=document,
            processor=processor,
        )

        self.debug(
            msg=Event.TaskCompleted.value,
            uid=uid,
            size=len(found),
        )


class PipelineFilterMask(GenericPipeline):
    """
    This pipeline uses mask to filter specific emails from the dataframe
    before storing them via Blackboard.
    """

    def process(
        self,
        processor: IProcessor,
        document: ITarget,
        *args,
        **kwargs,
    ) -> None:

        super().process(processor=processor, document=document, *args, **kwargs)

        document_adaptee: DataFrameDocument = document.request()  # type: ignore

        id_list = [123456789]
        allowed_emails = ["example.org", "example.net"]
        pattern = "|".join(allowed_emails)

        data: pd.DataFrame = document_adaptee.content  # type: ignore
        mask_id = data["ID"].isin(id_list)
        mask_email = data["Email"].str.contains(pattern, regex=True)

        found = data[mask_id & mask_email]

        document_adaptee.update_content(found)

        identifier: str = processor.blackboard.write(  # type: ignore
            caller=self,
            document=document,
            processor=processor,
        )

        self.debug(
            msg=Event.TaskCompleted.value,
            identifier=identifier,
            size=len(found),
        )


# --------------------------------------------------------------------------- #
# Processors
# --------------------------------------------------------------------------- #


class ProcessorMockSQL(GenericProcessor):
    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: list,
        items: list,
        level: int = logging.NOTSET,
        handler: Optional[logging.Handler] = None,
        **kwargs,
    ):
        GenericProcessor.__init__(
            self,
            blackboard=blackboard,
            pipelines=pipelines,
            level=level,
            handler=handler,
            **kwargs,
        )

        self._items = items

    def create_generator(self) -> Generator[ITarget, None, None]:
        self.debug(msg=Event.Iterating.value, message="START")

        for order, item in enumerate(self._items, start=1):

            self.debug(msg=Event.Processing.value, order=order, item=item)

            yield self.blackboard.create(
                caller=self,
                order=order,
                sql=item,
                publisher="faker",
                connection="mock_connection",
            )

        self.debug(msg=Event.Iterating.value, message="END")


class SyntheticDataProcessor(GenericProcessor):
    def __init__(
        self,
        blackboard: IBlackboard,
        pipelines: list,
        items: list,
        size: int,
        level: int = logging.NOTSET,
        handler: Optional[logging.Handler] = None,
        **kwargs,
    ):
        GenericProcessor.__init__(
            self,
            blackboard=blackboard,
            pipelines=pipelines,
            level=level,
            handler=handler,
            **kwargs,
        )

        self._items = items
        self._size = size

        self.debug(
            msg=Event.Constructor.value,
            blackboard=blackboard.name,
            pipelines=[p.name for p in self._pipelines if isinstance(p, IPipeline)],
            items=self._items,
        )

    def create_generator(self) -> Generator[ITarget, None, None]:
        self.debug(msg=Event.Iterating.value, message="START")

        for structure in self._items:
            self.debug(msg=Event.Processing.value, structure=structure)
            data = {}
            for k, v in structure.items():
                data[k] = [v["fnc"](**v["kwargs"]) for n in range(1, self._size)]

            yield self.blackboard.create(caller=self, data=pd.DataFrame(data))

        self.debug(msg=Event.Iterating.value, message="END")


# --------------------------------------------------------------------------- #
# Main tests
# --------------------------------------------------------------------------- #


class RunTestForSyntheticDataProcessor(ICommand, AuditLogger):

    def __init__(self):
        def level_to_int(level: str) -> int:
            return getattr(logging, level.upper(), logging.INFO)

        self.config: Config = Config(Project(__file__, "tests").config)
        self.level: int = level_to_int(
            self.config.find(
                "project",
                "logging",
                "level",
            ),
        )

        super().__init__(level=self.level)
        self.ff = Faker()
        self.items = [
            {
                "ID": {"fnc": self.ff.random_number, "kwargs": {"digits": 9}},
                "Created": {
                    "fnc": self.ff.date_time_between,
                    "kwargs": {"start_date": datetime(2017, 1, 1)},
                },
                "Created by": {"fnc": self.ff.name, "kwargs": {}},
                "Description": {"fnc": self.ff.sentence, "kwargs": {"nb_words": 10}},
                "Email": {"fnc": self.ff.email, "kwargs": {}},
            },
            {
                "id": {"fnc": self.ff.random_number, "kwargs": {"digits": 9}},
                "datum": {
                    "fnc": self.ff.date_time_between,
                    "kwargs": {"start_date": datetime(2013, 1, 1)},
                },
                "person": {"fnc": self.ff.name, "kwargs": {}},
            },
        ]

        self.source_path: Optional[Path] = None
        self.temp_path: Optional[Path] = None

        self.info(
            msg=Event.Constructor.value,
            status="Completed!",
            level=self.level,
            config=self.config,
            items=self.items,
        )

        self.execute()

    def execute(self, *args, **kwargs) -> None:
        self.debug(msg=Event.Executing.value, *args, **kwargs)

        self._setup_paths()
        self._mock_sql_pipeline_process()
        self._synthetic_processor_and_data_pipline()
        self._synthetic_processor_and_cleanup_pipline()
        self._syntetic_data_process_filter()
        self._process_filter_with_mask()

        self.debug(
            msg=f"{self.name}.execute",
            status="Completed!",
            temp=str(self.temp_path),
        )

    def _create_blackboard_and_repository(
        self,
        strategy_create: type,
        startegy_read: type,
        strategy_write: type,
        write_on_flush: bool = False,
    ) -> GenericBlackboard:
        blackboard: GenericBlackboard = GenericBlackboard(
            strategy_create=strategy_create(level=self.level),  # type: ignore
            write_on_flush_only=write_on_flush,
            level=self.level,
        )

        # Create and registger Registry
        blackboard.register(
            GenericRepository(
                strategy_read=startegy_read(level=self.level),  # type: ignore
                strategy_write=strategy_write(level=self.level),  # type: ignore
                allowed=["storage_path"],
                storage_path=str(self.temp_path),
                level=self.level,
            )
        )
        return blackboard

    def _blackboard_flush_and_clear(self):

        if not self.blackboard.count > 0:
            raise RuntimeError(f"Blackboard count: {self.blackboard.count} > 0 FAIL!")

        self.blackboard.flush(self)
        self.blackboard.clear()

        if self.blackboard.count > 0:
            raise RuntimeError(f"Blackboard count: {self.blackboard.count} == 0 FAIL!")

    def _setup_paths(self):
        msg: str = "SETTING UP PATHS"
        self.debug(
            msg=msg,
            status="Starting ...",
        )

        from tempfile import mktemp

        self.temp_path = Path(mktemp(suffix="workflow"))
        self.temp_path.mkdir(exist_ok=True)
        self.source_path = Path(
            str(
                self.config.find(
                    "dev",
                    "processor-synthetic-data",
                    "source_path",
                )
            )
        )

        self.info(
            msg=msg,
            source_path=str(self.source_path.name),
            temp_path=str(self.temp_path),
            items=self.items,
            status="Completed!",
        )

    def _mock_sql_pipeline_process(self):
        msg: str = "Mockup SQL pipeline process ..."
        self.debug(msg=msg, status="Starting ...")

        # Create Blackboard
        self.blackboard: GenericBlackboard = self._create_blackboard_and_repository(
            strategy_create=StrategyCreateSimpleMock,
            startegy_read=StrategyReadSimpleMock,
            strategy_write=StrategyWriteSimpleMock,
        )

        processor = ProcessorMockSQL(
            blackboard=self.blackboard,
            pipelines=[PipelineTest(level=self.level)],
            items=[
                "SELECT * FROM original.document_pdf;",
                "SELECT * FROM transformed.document_pdf;",
            ],
            level=self.level,
        )

        processor.start()

        self._blackboard_flush_and_clear()

        self.info(msg=msg, status="Done!")

    def _synthetic_processor_and_data_pipline(self):
        msg: str = "Synthetic processor and data pipeline ..."
        self.debug(
            msg=msg,
            status="STARTING ...",
        )

        self.blackboard: GenericBlackboard = self._create_blackboard_and_repository(
            strategy_create=StrategyCreateDataFrame,
            startegy_read=StrategyReadSimpleMock,
            strategy_write=StrategyWriteDataFrame,
        )

        processor = SyntheticDataProcessor(
            blackboard=self.blackboard,
            pipelines=[PipelineSyntheticData(level=self.level)],
            items=self.items,
            size=100,
            level=self.level,
        )

        processor.start()

        self._blackboard_flush_and_clear()

        self.info(msg=msg, status="Done!")

    def _synthetic_processor_and_cleanup_pipline(self):
        msg: str = "Synthetic processor and cleanup pipeline ..."
        self.debug(msg=msg, status="Starting ...")

        self.blackboard: GenericBlackboard = self._create_blackboard_and_repository(
            strategy_create=StrategyCreateDataFrame,
            startegy_read=StrategyReadSimpleMock,
            strategy_write=StrategyWriteDataFrame,
        )

        processor = SyntheticDataProcessor(
            blackboard=self.blackboard,
            pipelines=[
                PipelineSyntheticData(level=self.level),
                PipelineCleanupData(level=self.level),
            ],
            items=self.items,
            size=100,
            level=self.level,
        )

        processor.start()

        self._blackboard_flush_and_clear()

        self.info(msg=msg, status="Done!")

    def _syntetic_data_process_filter(self):
        msg: str = "Process filter with synthetic data"
        self.debug(msg=msg, status="Starting ...")

        self.blackboard: GenericBlackboard = self._create_blackboard_and_repository(
            strategy_create=StrategyCreateDataFrame,
            startegy_read=StrategyReadSimpleMock,
            strategy_write=StrategyWriteDataFrame,
        )

        processor = SyntheticDataProcessor(
            blackboard=self.blackboard,
            pipelines=[
                PipelineSyntheticData(level=self.level),
                PipelineCleanupData(level=self.level),
                PipelineFilterQuery(level=self.level),
            ],
            items=self.items,
            size=100,
            level=self.level,
        )

        processor.start()

        self._blackboard_flush_and_clear()

        self.info(msg=msg, status="Done!")

    def _process_filter_with_mask(self):
        msg: str = "Process synthetic data with filtered mask pipeline ..."
        self.debug(msg=msg, status="Starting ...")

        self.blackboard: GenericBlackboard = self._create_blackboard_and_repository(
            strategy_create=StrategyCreateDataFrame,
            startegy_read=StrategyReadSimpleMock,
            strategy_write=StrategyWriteDataFrame,
        )

        processor = SyntheticDataProcessor(
            blackboard=self.blackboard,
            pipelines=[
                PipelineSyntheticData(level=self.level),
                PipelineCleanupData(level=self.level),
                PipelineFilterQuery(level=self.level),
                PipelineFilterMask(level=self.level),
            ],
            items=self.items,
            size=100,
            level=self.level,
        )

        processor.start()

        self._blackboard_flush_and_clear()

        self.info(msg=msg, status="Done!")


try:
    test = RunTestForSyntheticDataProcessor()
except Exception as e:
    print(str(e))

gc.collect()
