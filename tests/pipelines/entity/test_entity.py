# Module name: tests/pipelines/entity/test_entity.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""SyRS-PPL-entity and SyRS-PPL-entity-anchoring: the entity pipelines."""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

from wattleflow.concrete import Document, DocumentFacade
from wattleflow.concrete.exception import DriverException
from wattleflow.concrete.pipeline import PipelineError
from wattleflow.core import IProcessor
from wattleflow.drivers.identity import DriverIdentity, Identity, Result
from wattleflow.pipelines.entity import GenericEntityPipeline, PipelineEntityLink

from tests.drivers.identity.test_driver import KEY_ENV, driver


class Content(Document):
    __slots__ = ()

    @property
    def size(self) -> int:
        return len(self.content or "")


def facade(content) -> DocumentFacade:
    return DocumentFacade(Content(content))


def processor(identity_driver=None) -> Mock:
    stub = Mock(spec=IProcessor)
    stub.name = "processor"
    stub.driver = identity_driver
    return stub


def fake_driver(content="out") -> Mock:
    stub = Mock(spec=DriverIdentity)
    result = Result(content, [Identity((0, 3), "PER", "new", "⟦PER:AAAAAAAA⟧")])
    stub.read.return_value = result
    stub.write.return_value = result
    return stub


def link(**settings) -> PipelineEntityLink:
    return PipelineEntityLink(**{"namespace": "ids", "level": 50, **settings})


class BaseTest(unittest.TestCase):
    def test_a_text_document_gives_its_text(self):  # SyRS-PPL-entity UC01 k.1
        self.assertEqual(GenericEntityPipeline.source_of(facade("words")), "words")

    def test_a_dataset_document_gives_its_rows(self):  # UC01 k.2
        rows = [{"name": "Ann"}]
        self.assertEqual(GenericEntityPipeline.source_of(facade(rows)), rows)

    def test_a_document_without_either_gives_none(self):  # UC01 k.3
        self.assertIsNone(GenericEntityPipeline.source_of(facade(b"bytes")))

    def test_without_a_driver_the_error_names_the_processor_not_the_text(self):  # UC02 k.4
        with self.assertRaises(PipelineError) as raised:
            link().driver_of(processor(None))
        self.assertIn("processor", str(raised.exception))


class LinkTest(unittest.TestCase):
    def test_without_create_only_read_is_called(self):  # anchoring UC01 k.1
        d = fake_driver()
        link().transform(processor(d), facade("text"))
        d.read.assert_called_once()
        d.write.assert_not_called()

    def test_with_create_only_write_is_called(self):  # UC01 k.2
        d = fake_driver()
        link(create=True).transform(processor(d), facade("text"))
        d.write.assert_called_once()
        d.read.assert_not_called()

    def test_a_dataset_is_one_driver_call(self):  # UC01 k.3
        d = fake_driver([{"name": "x"}])
        link().transform(processor(d), facade([{"name": "Ann"}, {"name": "Bob"}]))
        self.assertEqual(d.read.call_count, 1)

    def test_a_driver_error_becomes_a_pipeline_error_without_entity_words(self):  # UC01 k.4
        d = fake_driver()
        d.read.side_effect = DriverException(caller=d, error="boom")
        with self.assertRaises(PipelineError) as raised:
            link().transform(processor(d), facade("John Smith"))
        self.assertNotIn("John Smith", str(raised.exception))
        self.assertIn("DriverException", str(raised.exception))

    def test_a_document_without_a_source_does_not_call_the_driver(self):  # UC01 k.5
        d = fake_driver()
        link().transform(processor(d), facade(b"bytes"))
        d.read.assert_not_called()

    def test_apply_replaces_the_content(self):  # UC02 k.6
        doc = facade("John")
        link().transform(processor(fake_driver("out")), doc)
        self.assertEqual(doc.request().content, "out")

    def test_without_apply_the_content_stays(self):  # UC02 k.7
        doc = facade("John")
        link(apply=False).transform(processor(fake_driver("out")), doc)
        self.assertEqual(doc.request().content, "John")

    @patch.dict(os.environ, {KEY_ENV: "test-secret"})
    def test_an_uncertain_entity_stays_in_the_content(self):  # UC02 k.8
        d = driver()
        doc = facade("Dr Jon Smith")
        with patch("wattleflow.drivers.identity.driver.Decision.decide", return_value=("uncertain", None)):
            d.write("ids", "Dr John Smith")
            link().transform(processor(d), doc)
        self.assertIn("Jon Smith", doc.request().content)

    def test_the_namespace_reaches_the_driver_as_uri(self):  # UC01 k.9
        d = fake_driver()
        link(namespace="people").transform(processor(d), facade("text"))
        self.assertEqual(d.read.call_args.args[0], "people")

    def test_a_missing_namespace_fails_at_assembly(self):
        with self.assertRaises(PipelineError):
            PipelineEntityLink(level=50)

    def test_the_result_is_a_count_not_content(self):
        self.assertEqual(link().transform(processor(fake_driver()), facade("text")), 1)


if __name__ == "__main__":
    unittest.main()
