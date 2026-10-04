# Module name: tests/test_flow_preconditions.py
# FRQ-PRC-01.22: the preconditions of the document flow are checks, not assertions. A blackboard needs a
# create strategy, takes only repositories; a processor takes only a blackboard, a list of pipelines and
# pipelines. Each refusal is the layer's own exception, and it survives `python -O`.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_flow_preconditions -v
import logging
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import MagicMock

from wattleflow.concrete.blackboard import GenericBlackboard
from wattleflow.concrete.exception import BlackboardException, ProcessorException
from wattleflow.concrete.processor import GenericProcessor
from wattleflow.core import IPipeline
from tests.test_blackboard import Board, Create, Repo

QUIET = {"level": logging.CRITICAL}


class Proc(GenericProcessor):
    __slots__ = ()

    def create_generator(self):
        return iter(())


class BlackboardChecksTest(unittest.TestCase):
    def test_a_create_strategy_is_required(self):
        class Bare(Board):
            __slots__ = ()

            def __init__(self, strategy):
                GenericBlackboard.__init__(self, strategy_create=strategy, canvas={}, **QUIET)

        for bad in (None, object(), "Create"):
            with self.subTest(bad=bad), self.assertRaises(BlackboardException):
                Bare(bad)
        Bare(Create())

    def test_only_a_repository_can_be_registered(self):
        board = Board(**QUIET)
        for bad in (object(), None, "repo"):
            with self.subTest(bad=bad), self.assertRaises(BlackboardException):
                board.register(bad)
        self.assertEqual(board.repositories, [])

    def test_a_repository_is_accepted(self):
        board = Board(**QUIET)
        board.register(Repo())
        self.assertEqual(len(board.repositories), 1)


class ProcessorChecksTest(unittest.TestCase):
    def test_the_constructor_takes_only_a_blackboard_and_a_list_of_pipelines(self):
        pipeline = MagicMock(spec=IPipeline)
        cases = (
            {"blackboard": object()},
            {"blackboard": "board"},
            {"pipelines": (pipeline,)},
            {"pipelines": pipeline},
        )
        for kwargs in cases:
            with self.subTest(kwargs=sorted(kwargs)), self.assertRaises(ProcessorException):
                Proc(**kwargs, **QUIET)

    def test_a_valid_blackboard_and_pipelines_are_accepted(self):
        Proc(blackboard=MagicMock(spec=GenericBlackboard), pipelines=[MagicMock(spec=IPipeline)], **QUIET)

    def test_register_blackboard_refuses_anything_else(self):
        processor = Proc(**QUIET)
        for bad in (object(), None):
            with self.subTest(bad=bad), self.assertRaises(ProcessorException):
                processor.register_blackboard(bad)
        self.assertIsNone(processor.blackboard)

    def test_register_pipeline_refuses_anything_else(self):
        processor = Proc(**QUIET)
        for bad in (object(), None):
            with self.subTest(bad=bad), self.assertRaises(ProcessorException):
                processor.register_pipeline(bad)
        self.assertEqual(processor._pipelines, [])

    def test_a_registered_pipeline_and_blackboard_are_kept(self):
        processor, pipeline = Proc(**QUIET), MagicMock(spec=IPipeline)
        board = MagicMock(spec=GenericBlackboard)
        processor.register_blackboard(board)
        processor.register_pipeline(pipeline)
        self.assertIs(processor.blackboard, board)
        self.assertEqual(processor._pipelines, [pipeline])


class OptimisedModeTest(unittest.TestCase):
    def test_the_refusals_survive_python_O(self):
        code = textwrap.dedent(
            """
            import logging
            from wattleflow.concrete.exception import ProcessorException, BlackboardException
            from wattleflow.concrete.processor import GenericProcessor

            class P(GenericProcessor):
                __slots__ = ()
                def create_generator(self):
                    return iter(())

            results = []
            for call in (lambda: P(blackboard=object(), level=logging.CRITICAL),
                         lambda: P(level=logging.CRITICAL).register_pipeline(object())):
                try:
                    call()
                except ProcessorException:
                    results.append("refused")
                else:
                    results.append("accepted")
            print(",".join(results))
            """
        )
        out = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "refused,refused", out.stderr[-300:])


if __name__ == "__main__":
    unittest.main()
