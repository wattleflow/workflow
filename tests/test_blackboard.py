# Module name: tests/test_blackboard.py
# Tests for concrete/blackboard.py — FRQ-BBD §9 criteria 1–5 and the closed §12 findings:
# the generic layer declares the key it injects (`defer_flush`), `TRANSITIONS`
# is exported, and the constructor/destructor contract holds.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest discover -s tests -t . -v
import gc
import unittest
from types import MappingProxyType
from unittest.mock import patch

from wattleflow.concrete import blackboard as module
from wattleflow.concrete.blackboard import GenericBlackboard, TRANSITIONS
from wattleflow.concrete.exception import BlackboardException
from wattleflow.concrete.repository import GenericRepository
from wattleflow.concrete.strategy import StrategyCreate, StrategyWrite
from wattleflow.core import IOriginator, IWattleflow
from wattleflow.decorators.preset import PresetGate


class Create(StrategyCreate):
    def execute(self, caller, **kwargs):
        return None


class Write(StrategyWrite):
    def execute(self, caller, **kwargs):
        return True


class Board(GenericBlackboard[dict]):
    """Minimal specialisation: no ALLOWED of its own, trivial abstract methods."""

    __slots__ = ()

    def __init__(self, **kwargs):
        super().__init__(strategy_create=Create(), canvas={}, **kwargs)

    @property
    def count(self) -> int:
        return len(self._canvas)

    def clean(self):
        self._canvas.clear()
        self._repositories.clear()

    def create(self, caller, **kwargs):
        return None

    def delete(self, identifier, **kwargs):
        self._canvas.pop(identifier, None)

    def flush(self, caller, **kwargs) -> bool:
        return False

    def read(self, identifier, **kwargs):
        return self._canvas[identifier]

    def write(self, pipeline, facade, **kwargs):
        return ""


class Repo(GenericRepository):
    """Minimal IRepository: the write strategy is required, nothing else."""

    __slots__ = ()

    def __init__(self):
        super().__init__(strategy_write=Write())


class Declaring(Board):
    __slots__ = ()
    ALLOWED = ["configuration"]


class DeferFlushDeclarationTest(unittest.TestCase):
    """§12 t.9: the key the generic layer injects is declared by the generic layer."""

    def test_generic_layer_declares_defer_flush(self):
        self.assertIn("defer_flush", PresetGate.resolve(GenericBlackboard))

    def test_specialisation_without_allowed_inherits_the_declaration(self):
        self.assertEqual(PresetGate.resolve(Board), {"defer_flush"})

    def test_specialisation_adds_only_its_own_keys(self):
        self.assertEqual(PresetGate.resolve(Declaring), {"defer_flush", "configuration"})

    def test_default_is_true_and_raises_no_warning(self):
        with patch.object(Board, "warning") as warning:
            board = Board()
        self.assertIs(board.defer_flush, True)
        warning.assert_not_called()

    def test_explicit_value_is_kept(self):
        with patch.object(Board, "warning") as warning:
            board = Board(defer_flush=False)
        self.assertIs(board.defer_flush, False)
        warning.assert_not_called()

    def test_declared_key_of_specialisation_is_accepted(self):
        with patch.object(Declaring, "warning") as warning:
            board = Declaring(configuration={"a": 1})
        self.assertEqual(board.configuration, {"a": 1})
        self.assertIs(board.defer_flush, True)
        warning.assert_not_called()

    def test_unknown_key_is_still_reported(self):
        with patch.object(Board, "warning") as warning:
            board = Board(bogus=1)
        warning.assert_called_once()
        self.assertEqual(warning.call_args.kwargs["discarded"], ["bogus"])
        with self.assertRaises(AttributeError):
            board.bogus

    def test_fmt_is_an_alias_for_formatting(self):
        with patch.object(Board, "warning") as warning:
            board = Board(fmt="%(message)s")
        warning.assert_not_called()
        with self.assertRaises(AttributeError):
            board.fmt


class ModuleContractTest(unittest.TestCase):
    """§9 criteria 1, 5 and §12 t.5."""

    def test_transitions_is_exported(self):
        self.assertIn("TRANSITIONS", module.__all__)
        from wattleflow.concrete import TRANSITIONS as reexported
        self.assertIs(reexported, TRANSITIONS)

    def test_all_names_resolve(self):
        for name in module.__all__:
            self.assertTrue(hasattr(module, name), name)

    def test_wattleflow_precedes_generic_in_the_mro(self):
        mro = GenericBlackboard.__mro__
        self.assertLess(mro.index(IWattleflow), mro.index(module.Generic))

    def test_originator_mixin_linearises(self):
        class Snap(Board, IOriginator):
            __slots__ = ()

            def save_state(self):
                return None

            def restore_state(self, memento):
                return None

        self.assertIsInstance(Snap(), IOriginator)

    def test_slots_cover_the_five_members(self):
        self.assertEqual(
            set(GenericBlackboard.__slots__),
            {"_canvas", "_fsm", "_preset", "_repositories", "_strategy_create"},
        )

    def test_fail_from_every_non_terminal_state_and_clean_from_every_state(self):
        S, A = module.BlackboardState, module.BlackboardAction
        for state in (S.IDLE, S.READY, S.DIRTY):
            self.assertEqual(TRANSITIONS[(state, A.FAIL)], S.FAILED)
        for state in (S.IDLE, S.READY, S.DIRTY, S.FAILED):
            self.assertEqual(TRANSITIONS[(state, A.CLEAN)], S.CLEARED)
        self.assertFalse(hasattr(A, "READ"))


class AutomatonTest(unittest.TestCase):
    """§12 resolved t.1: the generic layer holds the automaton and refuses a transition the table does not allow."""

    def setUp(self):
        self.S, self.A = module.BlackboardState, module.BlackboardAction

    def test_new_board_is_idle(self):
        self.assertIs(Board().state, self.S.IDLE)

    def test_register_moves_to_ready(self):
        board = Board()
        board.register(Repo())
        self.assertIs(board.state, self.S.READY)

    def test_write_flush_cycle(self):
        board = Board()
        board.register(Repo())
        board._transition(self.A.WRITE)
        self.assertIs(board.state, self.S.DIRTY)
        board._transition(self.A.FLUSH)
        self.assertIs(board.state, self.S.READY)

    def test_refused_transition_raises_and_keeps_state(self):
        board = Board()
        with self.assertRaises(BlackboardException):
            board._transition(self.A.WRITE)
        self.assertIs(board.state, self.S.IDLE)

    def test_register_is_refused_after_clean(self):
        board = Board()
        self.assertTrue(board._try_transition(self.A.CLEAN))
        with self.assertRaises(BlackboardException):
            board.register(Repo())
        self.assertEqual(board.repositories, [])

    def test_register_is_refused_in_failed(self):
        board = Board()
        board._try_transition(self.A.FAIL)
        with self.assertRaises(BlackboardException):
            board.register(Repo())

    def test_try_transition_never_raises_and_is_repeatable(self):
        board = Board()
        self.assertTrue(board._try_transition(self.A.CLEAN))
        self.assertFalse(board._try_transition(self.A.CLEAN))
        self.assertFalse(board._try_transition(self.A.FAIL))
        self.assertIs(board.state, self.S.CLEARED)

    def test_specialisation_may_replace_its_own_fsm(self):
        """Specialisations in blackwattle still build their own `_fsm`."""
        from wattleflow.concrete.state_machine import StateMachine

        class Own(Board):
            __slots__ = ("_fsm",)

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._fsm = StateMachine(TRANSITIONS, self.S0, name="Own")

            S0 = module.BlackboardState.IDLE

        self.assertIs(Own().state, module.BlackboardState.IDLE)


class CanvasContractTest(unittest.TestCase):
    """§12 resolved t.3: `canvas` is a read-only Mapping[str, Item]."""

    def test_annotation_is_mapping_of_str_to_item(self):
        self.assertEqual(
            GenericBlackboard.canvas.fget.__annotations__["return"], "Mapping[str, Item]"
        )

    def test_empty_canvas_gives_an_empty_view(self):
        self.assertEqual(dict(Board().canvas), {})


class FlushContractTest(unittest.TestCase):
    """§12 resolved t.4: the contract of `flush` is written where the generic layer declares it."""

    def test_docstring_defines_the_outcome(self):
        doc = GenericBlackboard.flush.__doc__
        self.assertIn("every", doc)
        self.assertIn("False", doc)

    def test_flush_is_still_abstract_and_bool(self):
        self.assertIn("flush", GenericBlackboard.__abstractmethods__)
        self.assertEqual(GenericBlackboard.flush.__annotations__["return"], "bool")


class ConstructorContractTest(unittest.TestCase):
    """§9 criteria 2–4."""

    def test_strategy_create_is_checked_before_construction(self):
        class Bare(Board):
            __slots__ = ()

            def __init__(self):
                GenericBlackboard.__init__(self, strategy_create=object(), canvas={})

        with self.assertRaisesRegex(BlackboardException, "Expected StrategyCreate"):
            Bare()

    def test_del_survives_failed_construction_without_masking(self):
        class Bare(Board):
            __slots__ = ()

            def __init__(self):
                GenericBlackboard.__init__(self, strategy_create=object(), canvas={})

        with patch.object(Bare, "error") as error:
            try:
                Bare()
            except BlackboardException:
                pass
            gc.collect()
        error.assert_not_called()

    def test_canvas_is_a_read_only_view(self):
        board = Board()
        board._canvas["k"] = 1
        view = board.canvas
        self.assertIsInstance(view, MappingProxyType)
        self.assertEqual(view["k"], 1)
        with self.assertRaises(TypeError):
            view["k"] = 2

    def test_repositories_is_a_copy(self):
        board = Board()
        board.register(Repo())
        copy = board.repositories
        copy.clear()
        self.assertEqual(len(board.repositories), 1)

    def test_len_is_count(self):
        board = Board()
        board._canvas["k"] = 1
        self.assertEqual(len(board), 1)


class RegisterTest(unittest.TestCase):
    """`register` lives in the generic layer; the state transition is left to a hook."""

    def test_register_is_concrete_in_the_generic_layer(self):
        self.assertNotIn("register", GenericBlackboard.__abstractmethods__)
        self.assertIs(Board.register, GenericBlackboard.register)

    def test_repository_is_attached(self):
        board, repo = Board(), Repo()
        with patch.object(Board, "warning") as warning:
            board.register(repo)
        self.assertEqual(board.repositories, [repo])
        warning.assert_not_called()

    def test_non_repository_is_rejected(self):
        board = Board()
        with self.assertRaisesRegex(BlackboardException, "Expected IRepository"):
            board.register(object())
        self.assertEqual(board.repositories, [])

    def test_duplicate_is_reported_and_not_attached_twice(self):
        board, repo = Board(), Repo()
        board.register(repo)
        with patch.object(Board, "warning") as warning:
            board.register(repo)
        self.assertEqual(board.repositories, [repo])
        warning.assert_called_once()
        self.assertEqual(warning.call_args.kwargs["error"], "Repository already registered!")

    def test_hook_runs_once_per_attached_repository(self):
        board, repo = Board(), Repo()
        with patch.object(Board, "_registered") as hook, patch.object(Board, "warning"):
            board.register(repo)
            board.register(repo)
            board.register(Repo())
        self.assertEqual(hook.call_count, 2)
        hook.assert_any_call(repo)

    def test_hook_is_not_run_for_a_rejected_type(self):
        board = Board()
        with patch.object(Board, "_registered") as hook:
            with self.assertRaises(BlackboardException):
                board.register(object())
        hook.assert_not_called()

    def test_hook_runs_after_the_repository_is_in_the_list(self):
        seen = []

        class Observing(Board):
            __slots__ = ()

            def _registered(self, repository):
                seen.append(list(self._repositories))

        board, repo = Observing(), Repo()
        board.register(repo)
        self.assertEqual(seen, [[repo]])

    def test_default_hook_is_a_no_op(self):
        self.assertIsNone(GenericBlackboard._registered(Board(), Repo()))


if __name__ == "__main__":
    unittest.main()
