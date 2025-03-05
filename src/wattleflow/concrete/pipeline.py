# Module Name: core/concrete/pipeline.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains concrete pipeline classes.

from abc import abstractmethod
from wattleflow.core import IIterator
from wattleflow.core import IPipeline
from wattleflow.concrete.attribute import Attribute


"""
ETL Pipeline Library
====================

This library provides a structured framework for building ETL (Extract, Transform, Load)
pipelines using modular Python classes. The classes inherit from the `GenericPipeline`
parent class and are specialised for different ETL operations and data types.

## General Class Naming Pattern:
    class <ETLOperation><DataType>Pipeline(Pipeline)

Where:
- **`ETLOperation`** → Type of operation: `Extract`, `Transform`, `Load`
- **`DataType`** → Data type: `Document`, `File`, `Record`, `DataFrame`
- **`Pipeline`** → Indicates that this is an ETL pipeline

---

## Class Categories:

### 1. Extract Classes
Classes responsible for extracting data from different sources and processing it
   into a specific format.
- `ExtractDocumentPipeline` - Extracts data processed as documents (e.g., PDFs, JSON).
- `ExtractFilePipeline` - Extracts data from files (e.g., CSV, XML).
- `ExtractRecordPipeline` - Extracts individual records (e.g., rows from a database).
- `ExtractDataFramePipeline` - Extracts data as a Pandas DataFrame.

### 2. Transform Classes
Classes for processing and transforming extracted data.
- `TransformDocumentPipeline` - Processes documents (e.g., parsing, text tokenisation).
- `TransformFilePipeline` - Transforms entire files (e.g., format conversion).
- `TransformRecordPipeline` - Transforms individual records (e.g., data validation).
- `TransformDataFramePipeline` - Processes data in DataFrame format (e.g., aggregation).

### 3. Load Classes
Classes responsible for loading processed data into a target system.
- `LoadDocumentPipeline` - Loads data into document-based databases (e.g., MongoDB).
- `LoadFilePipeline` - Writes data into files (e.g., CSV, JSON).
- `LoadRecordPipeline` - Loads individual records into databases (SQL, NoSQL).
- `LoadDataFramePipeline` - Loads data into a Pandas DataFrame or analytical systems.


## Usage Examples:

### Extracting data from a CSV file and transforming it into a DataFrame:
```python
extractor = ExtractCsvDataFramePipeline()
data = extractor.process("data.csv")

transformer = TransformDataFramePipeline()
clean_data = transformer.process(data)

loader = LoadSqlRecordPipeline()
loader.process(clean_data)

"""


class GenericPipeline(IPipeline, Attribute):
    def __init__(self, *args, **kwargs):
        self.name = self.__class__.__name__

    @abstractmethod
    def process(self, processor, item, *args, **kwargs) -> None:
        self.evaluate(processor, IIterator)
