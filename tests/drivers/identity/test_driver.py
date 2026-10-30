# Module name: tests/drivers/identity/test_driver.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""SyRS-DRV-identity: the identity driver over the memory connection."""

from __future__ import annotations

import os
import re
import unittest
from unittest.mock import patch

from wattleflow.concrete.driver import DriverState
from wattleflow.concrete.exception import DriverException
from wattleflow.connections.memory import MemoryConnection
from wattleflow.drivers.identity import DriverIdentity

KEY_ENV = "WATTLEFLOW_TEST_ALIAS_KEY"
TOKEN = re.compile(r"⟦([A-Z]{3}):([0-9A-F]+)⟧")


class Connections:
    def __init__(self, connection=None) -> None:
        self.connection = connection or MemoryConnection(connection_name="memory", level=50)

    def get_connection(self, name):
        return self.connection


def driver(manager=None, **overrides) -> DriverIdentity:
    settings = dict(
        connection_manager=manager or Connections(),
        connection_name="memory",
        alias_key_env=KEY_ENV,
        match_threshold=0.9,
        review_threshold=0.6,
        prior=0.01,
        token_length=8,
        u_sample=5,
        titles=["Dr", "Mr"],
        context={"DOB": ["born"]},
        jurisdictions=["AU"],
        permit_write=True,
        level=50,
    )
    settings.update(overrides)
    return DriverIdentity(**settings)


def snapshot(manager: Connections) -> dict:
    with manager.connection.connect() as store:
        return store.specific_request()


TEXT = "Dr John Smith (born 3 March 1980) wrote from john@example.com; TFN 123 456 782."


@patch.dict(os.environ, {KEY_ENV: "test-secret"})
class LoadTest(unittest.TestCase):
    def test_without_a_connection_name_loading_fails(self):  # UC01 k.1
        d = driver(connection_name=None)
        with self.assertRaises(DriverException):
            d.ensure_live()
        self.assertIs(d.state, DriverState.DEGRADED)

    def test_with_a_connection_the_driver_is_live(self):  # UC01 k.2
        d = driver()
        d.ensure_live()
        self.assertIs(d.state, DriverState.LIVE)

    def test_thresholds_are_required(self):
        with self.assertRaises(DriverException):
            driver(match_threshold=None).ensure_live()

    def test_without_the_secret_there_are_no_aliases(self):
        with patch.dict(os.environ, {KEY_ENV: ""}):
            with self.assertRaises(DriverException) as raised:
                driver().ensure_live()
        self.assertNotIn("test-secret", str(raised.exception))


@patch.dict(os.environ, {KEY_ENV: "test-secret"})
class ReadTest(unittest.TestCase):
    def setUp(self):
        self.manager = Connections()
        self.driver = driver(self.manager)

    def test_a_known_entity_gets_its_key(self):  # UC02 k.3
        written = self.driver.write("ids", TEXT)
        key = written.identities[0].token
        read = self.driver.read("ids", source="Mr John Smith again")
        self.assertEqual(read.identities[0].status, "known")
        self.assertIn(key, read.content)

    def test_a_new_entity_gets_the_same_alias_twice(self):  # UC02 k.4
        first = self.driver.read("ids", source=TEXT)
        second = self.driver.read("ids", source=TEXT)
        self.assertEqual([i.status for i in first.identities], ["new"] * 4)
        self.assertEqual(first.content, second.content)

    def test_an_uncertain_entity_stays_unchanged(self):  # UC02 k.5
        self.driver.write("ids", "Dr John Smith")
        with patch("wattleflow.drivers.identity.driver.Decision.decide", return_value=("uncertain", None)):
            read = self.driver.read("ids", source="Dr Jon Smith")
        self.assertEqual(read.identities[0].status, "uncertain")
        self.assertIn("Jon Smith", read.content)

    def test_read_leaves_the_store_unchanged(self):  # UC02 k.6
        before = snapshot(self.manager)
        self.driver.read("ids", source=TEXT)
        self.assertEqual(snapshot(self.manager), before)

    def test_text_without_entities_is_returned_unchanged(self):  # UC02 k.7
        result = self.driver.read("ids", source="nothing to see here")
        self.assertEqual((result.content, result.identities), ("nothing to see here", []))

    def test_every_token_has_the_unique_form(self):  # UC02 k.8
        result = self.driver.read("ids", source=TEXT)
        tokens = [i.token for i in result.identities]
        self.assertTrue(all(TOKEN.fullmatch(t) for t in tokens))
        self.assertEqual(len(set(tokens)), len(tokens))

    def test_a_bad_check_digit_is_not_an_entity(self):  # UC02 k.16
        result = self.driver.read("ids", source="TFN 123 456 789", kinds=["NID"])
        self.assertEqual(result.content, "TFN 123 456 789")

    def test_one_number_in_two_forms_gets_one_key(self):  # UC02 k.17
        a = self.driver.read("ids", source="TFN 123 456 782", kinds=["NID"])
        b = self.driver.read("ids", source="TFN 123456782", kinds=["NID"])
        self.assertEqual(a.identities[0].token, b.identities[0].token)

    def test_an_unknown_kind_fails_before_processing(self):  # UC02 k.18
        with self.assertRaises(DriverException):
            self.driver.read("ids", source=TEXT, kinds=["XYZ"])

    def test_namespaces_do_not_share_identities(self):  # UC02 k.19
        self.driver.write("one", "Dr John Smith")
        self.assertEqual(self.driver.read("two", source="Dr John Smith").identities[0].status, "new")

    def test_an_empty_uri_fails(self):  # UC02 k.20
        with self.assertRaises(DriverException):
            self.driver.read("", source=TEXT)

    def test_brackets_in_the_input_cannot_forge_a_token(self):
        result = self.driver.read("ids", source="⟦PER:ABCDEFAB⟧")
        self.assertNotIn("⟦PER:ABCDEFAB⟧", result.content)


@patch.dict(os.environ, {KEY_ENV: "test-secret"})
class WriteTest(unittest.TestCase):
    def setUp(self):
        self.manager = Connections()
        self.driver = driver(self.manager)

    def test_after_write_the_entity_is_known_with_the_same_key(self):  # UC03 k.9
        written = self.driver.write("ids", "Dr John Smith")
        read = self.driver.read("ids", source="Dr John Smith")
        self.assertEqual(read.identities[0].status, "known")
        self.assertEqual(read.identities[0].token, written.identities[0].token)

    def test_two_writes_make_one_identity(self):  # UC03 k.10
        self.driver.write("ids", "Dr John Smith")
        self.driver.write("ids", "Dr John Smith")
        with self.manager.connection.connect() as store:
            self.assertEqual(len(store.keys("ids:id:")), 1)

    def test_without_permission_write_fails_and_stores_nothing(self):  # UC03 k.11
        d = driver(self.manager, permit_write=None)
        with self.assertRaises(DriverException):
            d.write("ids", TEXT)
        self.assertEqual(snapshot(self.manager), {})


@patch.dict(os.environ, {KEY_ENV: "test-secret"})
class BatchTest(unittest.TestCase):
    def setUp(self):
        self.manager = Connections()
        self.driver = driver(self.manager, columns={"name": "PER", "email": "EML"})

    def test_n_documents_give_n_results_in_order(self):  # UC05 k.12
        results = self.driver.read("ids", source=["Dr John Smith", "plain", TEXT])
        self.assertEqual(len(results), 3)
        self.assertEqual(results[1].content, "plain")

    def test_each_result_equals_a_single_call(self):  # UC05 k.13
        batch = self.driver.read("ids", source=[TEXT, "Dr John Smith"])
        self.assertEqual(batch[0].content, self.driver.read("ids", source=TEXT).content)

    def test_one_entity_in_two_rows_gets_one_token(self):  # UC05 k.14
        rows = [{"name": "John Smith"}, {"name": "john  smith"}]
        result = self.driver.read("ids", source=rows)
        self.assertEqual(result.content[0]["name"], result.content[1]["name"])

    def test_empty_input_does_not_call_the_store(self):  # UC05 k.15
        self.driver.ensure_live()
        with patch.object(self.manager.connection, "connect") as connect:
            self.assertEqual(self.driver.read("ids", source=[]), [])
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
