# Module name: tests/blackboards/test_small.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""SmallBlackboard: one facade on the canvas; flush tells whether every repository confirmed it."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wattleflow.blackboards.small import SmallBlackboard
from wattleflow.concrete.blackboard import BlackboardState
from wattleflow.concrete.exception import BlackboardException

from tests.blackboards.fakes import Create, facade, pipeline, processor, repository, warnings_of, written


def board(**kwargs) -> SmallBlackboard:
    return SmallBlackboard(strategy_create=Create(), **kwargs)


class TestSmallBlackboard(unittest.TestCase):
    def test_register_once(self):
        small, repo = board(), repository()
        small.register(repo)
        with warnings_of(SmallBlackboard, small) as warned:
            small.register(repo)
        self.assertEqual(len(warned), 1)
        self.assertEqual(small._fsm.state, BlackboardState.READY)
        with self.assertRaises(AssertionError):
            small.register(object())

    def test_write_without_a_repository_is_refused(self):
        with patch.object(SmallBlackboard, "exception"), self.assertRaises(BlackboardException):
            board().write(pipeline(), facade())

    def test_the_canvas_holds_one_facade(self):
        small = board()
        small.register(repository())
        first, second = facade("one"), facade("two")
        self.assertEqual(small.write(pipeline(), first), first.identifier)
        small.write(pipeline(), second)
        self.assertEqual(small.count, 1)
        self.assertIs(small.read("any"), second)
        self.assertEqual(small._fsm.state, BlackboardState.DIRTY)

    def test_write_checks_its_arguments(self):
        small = board()
        small.register(repository())
        with self.assertRaises(AssertionError):
            small.write(object(), facade())
        with self.assertRaises(AssertionError):
            small.write(pipeline(), object())

    def test_read_of_an_empty_canvas_is_refused(self):
        with self.assertRaises(BlackboardException):
            board().read("missing")

    def test_flush_writes_the_facade_and_confirms(self):
        small, repo = board(), repository()
        small.register(repo)
        document = facade()
        small.write(pipeline(), document)
        self.assertEqual(written(repo), [])  # defer_flush is the default
        self.assertTrue(small.flush(processor()))
        self.assertEqual(written(repo), [document.identifier])
        self.assertIs(repo.write.call_args.kwargs["caller"], small)
        self.assertEqual(small.count, 0)
        self.assertEqual(small._fsm.state, BlackboardState.READY)

    def test_flush_is_not_confirmed_when_a_repository_declines(self):
        small = board()
        small.register(repository("yes"))
        small.register(repository("no", confirms=False))
        small.write(pipeline(), facade())
        self.assertFalse(small.flush(processor()))

    def test_flush_of_an_empty_canvas_is_not_confirmed(self):
        small = board()
        small.register(repository())
        self.assertFalse(small.flush(processor()))

    def test_flush_is_called_by_a_processor_or_a_blackboard(self):
        with self.assertRaises(AssertionError):
            board().flush(object())

    def test_a_failing_repository_fails_the_blackboard(self):
        small, repo = board(), repository()
        repo.write.side_effect = OSError("disk")
        small.register(repo)
        small.write(pipeline(), facade())
        with self.assertRaises(BlackboardException):
            small.flush(processor())
        self.assertEqual(small._fsm.state, BlackboardState.FAILED)

    def test_eager_write_when_flush_is_not_deferred(self):
        small, repo = board(defer_flush=False), repository()
        small.register(repo)
        document = facade()
        small.write(pipeline(), document)
        self.assertEqual(written(repo), [document.identifier])
        self.assertEqual(small.count, 0)

    def test_create_hands_itself_to_the_strategy(self):
        small, caller = board(), processor()
        with patch.object(Create, "create", return_value="made") as create:
            self.assertEqual(small.create(caller, extra=1), "made")
        kwargs = create.call_args.kwargs
        self.assertIs(kwargs["caller"], small)
        self.assertIs(kwargs["blackboard"], small)
        self.assertIs(kwargs["processor"], caller)
        self.assertEqual(kwargs["extra"], 1)
        with self.assertRaises(AssertionError):
            small.create(object())

    def test_clean_flushes_what_was_left(self):
        small, repo = board(), repository()
        small.register(repo)
        document = facade()
        small.write(pipeline(), document)
        with warnings_of(SmallBlackboard, small) as warned:
            small.clear()
        self.assertEqual(len(warned), 1)
        self.assertEqual(written(repo), [document.identifier])
        self.assertEqual(small._fsm.state, BlackboardState.CLEARED)

    def test_delete_empties_the_canvas(self):
        small = board()
        small.register(repository())
        small.write(pipeline(), facade())
        with patch.object(SmallBlackboard, "warning"):
            small.delete("any")
        self.assertEqual(small.count, 0)


if __name__ == "__main__":
    unittest.main()
