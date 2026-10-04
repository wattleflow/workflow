# Module name: tests/test_processor_flush_key.py
# FRQ-BBD §12 (resolved t.5) and FRQ-PRC: the processor knows `flush_per_cycle` only;
# the retired `defer_flush` is an unknown key like any other.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest discover -s tests -t . -v
import unittest
from unittest.mock import patch

from wattleflow.concrete.processor import GenericProcessor


class Processor(GenericProcessor):
    __slots__ = ()

    def create_generator(self):
        return iter(())


class FlushKeyTest(unittest.TestCase):
    def test_default_is_per_cycle(self):
        self.assertIs(Processor().flush_per_cycle, True)

    def test_explicit_value_is_kept(self):
        self.assertIs(Processor(flush_per_cycle=False).flush_per_cycle, False)

    def test_defer_flush_is_reported_as_unknown_and_not_translated(self):
        with patch.object(Processor, "warning") as warning:
            processor = Processor(defer_flush=True)
        self.assertIs(processor.flush_per_cycle, True)
        self.assertTrue(warning.called)
        self.assertEqual(warning.call_args.kwargs.get("discarded"), ["defer_flush"])
        for call in warning.call_args_list:
            self.assertNotIn("deprecated", call.kwargs)


if __name__ == "__main__":
    unittest.main()
