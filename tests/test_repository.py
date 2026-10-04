# Module name: tests/test_repository.py
# Tests for GenericRepository and RepositoryWithDriver (FRQ-REP): construction checks that survive
# `python -O`, read and write through strategies with the caller handed over as the repository, the
# counter, failures as RepositoryException with the cause, bad input answered with the same exception
# (not an AttributeError from the report itself), and identity-based equality and hashing.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_repository -v
import logging
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import MagicMock

from wattleflow.concrete.blackboard import GenericBlackboard
from wattleflow.concrete.driver import GenericDriver
from wattleflow.concrete.exception import RepositoryException
from wattleflow.concrete.repository import GenericRepository, RepositoryWithDriver
from wattleflow.concrete.strategy import StrategyRead, StrategyWrite
from wattleflow.core import ITarget

QUIET = {"level": logging.CRITICAL}


class Write(StrategyWrite):
    def __init__(self, result=True, fail=False, **kwargs):
        super().__init__(**{**QUIET, **kwargs})
        self.result, self.fail, self.calls = result, fail, []

    def execute(self, caller, facade, **kwargs):
        self.calls.append((caller, facade, kwargs))
        if self.fail:
            raise RuntimeError("write down")
        return self.result


class Read(StrategyRead):
    def __init__(self, fail=False, **kwargs):
        super().__init__(**{**QUIET, **kwargs})
        self.fail, self.calls = fail, []

    def execute(self, caller, identifier=None, **kwargs):
        self.calls.append((caller, identifier, kwargs))
        if self.fail:
            raise RuntimeError("read down")
        return "document"


def facade(uid="u1"):
    target = MagicMock(spec=ITarget)
    target.identifier = uid
    return target


def board():
    blackboard = MagicMock(spec=GenericBlackboard)
    blackboard.name = "board"
    return blackboard


def make(write=None, read=None, **kwargs):
    return Plain(
        strategy_write=write or Write(), strategy_read=read, **{**QUIET, **kwargs}
    )


class Plain(GenericRepository):
    __slots__ = ()


class WithContext(GenericRepository):
    __slots__ = ()

    def _strategy_context(self):
        return {"extra": "x"}


class ConstructionTest(unittest.TestCase):
    def test_a_write_strategy_of_the_wrong_type_is_refused(self):
        for bad in (None, object(), Read()):
            with self.subTest(bad=bad), self.assertRaises(RepositoryException):
                Plain(strategy_write=bad, **QUIET)

    def test_a_read_strategy_of_the_wrong_type_is_refused(self):
        with self.assertRaises(RepositoryException):
            Plain(strategy_write=Write(), strategy_read=Write(), **QUIET)

    def test_the_checks_survive_optimised_mode(self):
        code = textwrap.dedent(
            """
            import logging
            from wattleflow.concrete.exception import RepositoryException
            from wattleflow.concrete.repository import GenericRepository

            class R(GenericRepository):
                __slots__ = ()

            try:
                R(strategy_write=object(), level=logging.CRITICAL)
            except RepositoryException:
                print("refused")
            else:
                print("accepted")
            """
        )
        out = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "refused", out.stderr[-300:])

    def test_a_driver_variant_needs_a_driver(self):
        class WithDriver(RepositoryWithDriver):
            __slots__ = ()

        for bad in (None, object()):
            with self.subTest(bad=bad), self.assertRaises(RepositoryException):
                WithDriver(strategy_write=Write(), driver=bad, **QUIET)

    def test_the_driver_reaches_the_strategy_through_the_context(self):
        driver = MagicMock(spec=GenericDriver)
        strategy = Write()
        repository = RepositoryWithDriver(strategy_write=strategy, driver=driver, **QUIET)
        repository.write(board(), facade())
        self.assertIs(strategy.calls[0][2]["driver"], driver)


class WriteTest(unittest.TestCase):
    def test_write_hands_the_repository_over_as_the_caller_and_counts_a_true_result(self):
        strategy, target = Write(), facade()
        repository = make(strategy)
        self.assertTrue(repository.write(board(), target))
        caller, written, kwargs = strategy.calls[0]
        self.assertIs(caller, repository)
        self.assertIs(written, target)
        self.assertIs(kwargs["repository"], repository)
        self.assertEqual(repository.count, 1)

    def test_a_false_result_is_not_counted(self):
        repository = make(Write(result=False))
        self.assertFalse(repository.write(board(), facade()))
        self.assertEqual(repository.count, 0)

    def test_clear_resets_the_counter(self):
        repository = make()
        repository.write(board(), facade())
        repository.clear()
        self.assertEqual(repository.count, 0)

    def test_the_context_and_extra_keywords_reach_the_strategy(self):
        strategy = Write()
        repository = WithContext(strategy_write=strategy, **QUIET)
        repository.write(board(), facade(), more=1)
        self.assertEqual(strategy.calls[0][2]["extra"], "x")
        self.assertEqual(strategy.calls[0][2]["more"], 1)

    def test_a_strategy_failure_is_a_repository_exception_with_its_cause_and_context(self):
        repository = WithContext(strategy_write=Write(fail=True), **QUIET)
        with self.assertRaises(RepositoryException) as caught:
            repository.write(board(), facade("doc-7"))
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        text = str(caught.exception)
        for part in ("doc-7", "board", "extra=str", "RuntimeError", "write down"):
            self.assertIn(part, text)

    def test_a_caller_that_is_not_a_blackboard_is_a_repository_exception(self):
        for caller in (object(), None, "board"):
            with self.subTest(caller=caller), self.assertRaises(RepositoryException):
                make().write(caller, facade())

    def test_a_facade_that_is_not_a_target_is_a_repository_exception(self):
        for bad in (object(), None):
            with self.subTest(bad=bad), self.assertRaises(RepositoryException):
                make().write(board(), bad)

    def test_a_rejected_write_does_not_reach_the_strategy(self):
        strategy = Write()
        with self.assertRaises(RepositoryException):
            make(strategy).write(object(), facade())
        self.assertEqual(strategy.calls, [])


class ReadTest(unittest.TestCase):
    def test_read_without_a_strategy_warns_and_answers_none(self):
        repository = Plain(strategy_write=Write(), level=logging.DEBUG)
        with self.assertLogs(level=logging.WARNING):
            self.assertIsNone(repository.read("x"))

    def test_read_hands_the_repository_over_as_the_caller(self):
        strategy = Read()
        repository = make(read=strategy)
        self.assertEqual(repository.read("x", key=1), "document")
        caller, identifier, kwargs = strategy.calls[0]
        self.assertIs(caller, repository)
        self.assertEqual((identifier, kwargs["key"]), ("x", 1))

    def test_a_read_failure_is_a_repository_exception_with_its_cause(self):
        repository = make(read=Read(fail=True))
        with self.assertRaises(RepositoryException) as caught:
            repository.read("x")
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)


class IdentityTest(unittest.TestCase):
    def test_equality_is_identity(self):
        a, b = make(), make()
        self.assertEqual(a, a)
        self.assertNotEqual(a, b)

    def test_hash_works_and_is_stable(self):
        a = make()
        self.assertEqual(hash(a), hash(a))
        self.assertEqual(len({a, make()}), 2)

    def test_comparing_writes_no_audit_record(self):
        other = make()  # first: the logger is shared per class and the last explicit level wins
        repository = Plain(strategy_write=Write(), level=logging.DEBUG)
        with self.assertNoLogs(level=logging.DEBUG):
            _ = repository == other

    def test_repr_names_the_class_the_strategy_context_and_the_counter(self):
        repository = WithContext(strategy_write=Write(), **QUIET)
        self.assertIn("WithContext", repr(repository))
        self.assertIn(":0]", repr(repository))

    def test_an_unbuilt_repository_answers_a_missing_name_with_that_name(self):
        bare = Plain.__new__(Plain)
        with self.assertRaises(AttributeError) as caught:
            _ = bare.anything
        self.assertIn("anything", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
