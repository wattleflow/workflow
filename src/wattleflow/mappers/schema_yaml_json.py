# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2025 WattleFlow
# License: Apache 2 Licence

import yaml, jsonschema
import pandas as pd


class ColumnMapper:
    def __init__(self, mapping: dict):
        self.mapping = mapping

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.rename(columns=self.mapping)


class SchemaValidator:
    def __init__(self, schema: dict):
        self.schema = schema

    def validate_row(self, row: dict):
        jsonschema.validate(instance=row, schema=self.schema)


class MapperSchemaYAML2JSON:  # Facade
    def __init__(self, mapper: ColumnMapper, validator: SchemaValidator):
        self.mapper = mapper
        self.validator = validator

    @classmethod
    def from_yaml(cls, cfg_str: str):
        cfg = yaml.safe_load(cfg_str)
        return cls(ColumnMapper(cfg["mapping"]), SchemaValidator(cfg["json_schema"]))

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df2 = self.mapper.apply(df)
        for rec in df2.to_dict(orient="records"):
            self.validator.validate_row(rec)
        return df2
