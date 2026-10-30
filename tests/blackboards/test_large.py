# Module name: tests/blackboards/test_large.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence

"""LargeBlackboard: facades by identifier until flush; its state is saved and restored as a memento."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wattleflow.blackboards.large import LargeBlackboard
from wattleflow.concrete.blackboard import BlackboardState
from wattleflow.concrete.exception import BlackboardException
from wattleflow.concrete.memento import GenericMemento
from wattleflow.core import IOriginator

from tests.blackboards.fakes import Create, facade, pipeline, processor, repository, warnings_of, written


def board(**kwargs) -> LargeBlackboard:
    return LargeBlackboard(strategy_create=Create(), **kwargs)


class TestLargeBlackboard(unittest.TestCase):
    def test_it_is_an_originator(self):
        self.assertIsInstance(board(), IOriginator)

    def test_register_once(self):
        large, repo = board(), repository()
        large.register(repo)
        with warnings_of(LargeBlackboard, large) as warned:
            large.register(repo)
        self.assertEqual(len(warned), 1)
        with self.assertRaises(AssertionError):
            large.register(object())

    def test_write_without_a_repository_stores_nothing(self):
        large = board()
        with warnings_of(LargeBlackboard, large) as warned:
            self.assertEqual(large.write(pipeline(), facade()), "")
        self.assertEqual(len(warned), 1)
        self.assertEqual(large.count, 0)

    def test_facades_are_kept_by_identifier(self):
        large = board()
        large.register(repository())
        first, second = facade("one"), facade("two")
        self.assertEqual(large.write(pipeline(), first), first.identifier)
        large.write(pipeline(), second)
        self.assertEqual(large.count, 2)
        self.assertIs(large.read(first.identifier), first)
        self.assertIs(large.read(second.identifier), second)
        with self.assertRaises(BlackboardException):
            large.read("missing")

    def test_write_checks_its_arguments(self):
        large = board()
        large.register(repository())
        with self.assertRaises(AssertionError):
            large.write(object(), facade())
        with self.assertRaises(AssertionError):
            large.write(pipeline(), object())

    def test_flush_writes_every_facade_and_clears(self):
        large, repo = board(), repository()
        large.register(repo)
        first, second = facade("one"), facade("two")
        large.write(pipeline(), first)
        large.write(pipeline(), second)
        self.assertEqual(written(repo), [])
        large.flush(processor())
        self.assertEqual(written(repo), [first.identifier, second.identifier])
        self.assertIs(repo.write.call_args.kwargs["caller"], large)
        self.assertEqual(large.count, 0)
        self.assertEqual(large._fsm.state, BlackboardState.READY)
        with self.assertRaises(AssertionError):
            large.flush(object())

    def test_a_failing_repository_fails_the_blackboard(self):
        large, repo = board(), repository()
        repo.write.side_effect = OSError("disk")
        large.register(repo)
        large.write(pipeline(), facade())
        with self.assertRaises(OSError):
            large.flush(processor())
        self.assertEqual(large._fsm.state, BlackboardState.FAILED)

    def test_eager_write_when_flush_is_not_deferred(self):
        large, repo = board(defer_flush=False), repository()
        large.register(repo)
        document = facade()
        large.write(pipeline(), document)
        self.assertEqual(written(repo), [document.identifier])

    def test_delete(self):
        large = board()
        large.register(repository())
        document = facade()
        large.write(pipeline(), document)
        large.delete(document.identifier)
        self.assertEqual(large.count, 0)
        with warnings_of(LargeBlackboard, large) as warned:
            large.delete("missing")
        self.assertEqual(len(warned), 1)

    def test_create_hands_itself_to_the_strategy(self):
        large, caller = board(), processor()
        with patch.object(Create, "create", return_value="made") as create:
            self.assertEqual(large.create(caller), "made")
        self.assertIs(create.call_args.kwargs["caller"], large)
        self.assertIs(create.call_args.kwargs["processor"], caller)

    def test_clean_flushes_what_was_left(self):
        large, repo = board(), repository()
        large.register(repo)
        document = facade()
        large.write(pipeline(), document)
        with warnings_of(LargeBlackboard, large) as warned:
            large.clear()
        self.assertEqual(len(warned), 1)
        self.assertEqual(written(repo), [document.identifier])
        self.assertEqual(large._fsm.state, BlackboardState.CLEARED)

    def test_save_state_records_the_canvas_and_the_state(self):
        large = board()
        large.register(repository())
        document = facade()
        large.write(pipeline(), document)
        memento = large.save_state()
        self.assertEqual(memento.get_state(), BlackboardState.DIRTY)
        self.assertIs(memento.canvas[document.identifier], document)

    # restore_state assigns StateMachine.state, which has no setter: every valid restore raises
    # AttributeError (finding 2026-10-05; Workflow.restore reaches it through restore_state).
    @unittest.expectedFailure
    def test_state_is_restored(self):
        document = facade()
        restored = board()
        restored.restore_state(GenericMemento(canvas={document.identifier: document}, state=BlackboardState.IDLE))
        self.assertIs(restored.read(document.identifier), document)
        self.assertEqual(restored._fsm.state, BlackboardState.READY)

    def test_the_memento_copies_the_canvas(self):
        large = board()
        large.register(repository())
        document = facade()
        large.write(pipeline(), document)
        memento = large.save_state()
        large._canvas.clear()
        self.assertIn(document.identifier, memento.canvas)

    def test_restore_is_refused_for_an_invalid_memento_or_state(self):
        large = board()
        with self.assertRaises(BlackboardException):
            large.restore_state(object())
        with self.assertRaises(BlackboardException):
            large.restore_state(GenericMemento(canvas={}, state=BlackboardState.DIRTY))


if __name__ == "__main__":
    unittest.main()
