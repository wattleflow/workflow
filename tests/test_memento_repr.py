# Module name: tests/test_memento_repr.py
# FRQ-MEM (DEF-MEM-02): repr(GenericMemento) names the snapshot and its keys, never the values
# (BR-PTN-04, NFRQ-SEC-06); the values stay reachable through get_state() and to_dict().
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_memento_repr -v
import unittest

from wattleflow.concrete.memento import GenericMemento


class MementoReprTest(unittest.TestCase):
    def test_values_are_not_printed(self):
        text = repr(GenericMemento(token="s3cret", state=3, nested={"password": "hunter2"}))
        for secret in ("s3cret", "hunter2", "password"):
            self.assertNotIn(secret, text)

    def test_keys_are_printed_in_payload_order(self):
        text = repr(GenericMemento(cycle=2, state=1))
        self.assertLess(text.index("cycle"), text.index("state"))

    def test_the_class_name_is_printed(self):
        self.assertIn("GenericMemento", repr(GenericMemento(a=1)))

    def test_an_empty_snapshot_has_a_repr(self):
        self.assertIn("GenericMemento", repr(GenericMemento()))

    def test_the_values_stay_reachable(self):
        memento = GenericMemento(token="s3cret", state=3)
        self.assertEqual(memento.to_dict(), {"token": "s3cret", "state": 3})
        self.assertEqual(memento.get_state(), 3)
        self.assertEqual(memento.token, "s3cret")


if __name__ == "__main__":
    unittest.main()
