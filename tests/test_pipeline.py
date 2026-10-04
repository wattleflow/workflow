# Module name: tests/test_pipeline.py
# Tests for GenericPipeline (FRQ-PIP): process is the frame around transform (input check, DEBUG trace
# only, every failure carried as PipelineError with its cause), and the object is safe to build, fail
# to build, and discard.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_pipeline -v
import logging
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import MagicMock

from wattleflow.concrete.exception import PipelineException
from wattleflow.concrete.pipeline import GenericPipeline, PipelineError
from wattleflow.core import IProcessor, ITarget


class Doubler(GenericPipeline):
    ALLOWED = ["flag"]

    def __init__(self, **kwargs):
        super().__init__(level=logging.DEBUG, **kwargs)
        self.calls = []

    def transform(self, processor, facade, **kwargs):
        self.calls.append((processor, facade, kwargs))
        return 2


class Failing(Doubler):
    def transform(self, processor, facade, **kwargs):
        raise ValueError("transform down")


def inputs():
    return MagicMock(spec=IProcessor), MagicMock(spec=ITarget)


class ContractTest(unittest.TestCase):
    def test_transform_is_abstract(self):
        class NoTransform(GenericPipeline):
            pass

        with self.assertRaises(TypeError):
            NoTransform()

    def test_process_passes_the_arguments_to_transform(self):
        pipeline, (processor, facade) = Doubler(), inputs()
        pipeline.process(processor, facade, key="v")
        self.assertEqual(pipeline.calls, [(processor, facade, {"key": "v"})])

    def test_the_slots_declare_the_preset(self):
        self.assertEqual(GenericPipeline.__slots__, ("_preset",))

    def test_a_declared_key_is_read_through_the_preset(self):
        self.assertEqual(Doubler(flag=3).flag, 3)

    def test_the_repr_is_the_class_name(self):
        self.assertEqual(repr(Doubler()), "Doubler")


class AuditTest(unittest.TestCase):
    def test_the_operation_opens_before_the_work_and_closes_after_it(self):
        pipeline, (processor, facade) = Doubler(), inputs()
        with self.assertLogs(level=logging.DEBUG) as logged:
            pipeline.process(processor, facade)
        text = "\n".join(logged.output)
        self.assertLess(text.index("Started"), text.index("Completed"))

    def test_this_layer_writes_nothing_above_debug(self):
        pipeline, (processor, facade) = Doubler(), inputs()
        with self.assertLogs(level=logging.DEBUG) as logged:
            pipeline.process(processor, facade)
        self.assertEqual({r.levelno for r in logged.records} - {logging.DEBUG}, set())

    def test_a_failure_is_traced_at_debug_and_never_at_error(self):
        pipeline, (processor, facade) = Failing(), inputs()
        with self.assertLogs(level=logging.DEBUG) as logged, self.assertRaises(PipelineError):
            pipeline.process(processor, facade)
        self.assertIn("Failed", "\n".join(logged.output))
        self.assertEqual({r.levelno for r in logged.records} - {logging.DEBUG}, set())


class FailureTest(unittest.TestCase):
    def test_a_transform_failure_is_a_pipeline_error_with_its_cause(self):
        pipeline, (processor, facade) = Failing(), inputs()
        with self.assertRaises(PipelineError) as caught:
            pipeline.process(processor, facade)
        self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertIn("Failing.process error: transform down", str(caught.exception))

    def test_the_error_names_the_pipeline_that_failed(self):
        pipeline, (processor, facade) = Failing(), inputs()
        with self.assertRaises(PipelineError) as caught:
            pipeline.process(processor, facade)
        self.assertIs(caught.exception.caller, pipeline)

    def test_a_processor_that_is_not_one_is_rejected_before_transform(self):
        pipeline = Doubler()
        with self.assertRaises(PipelineError) as caught:
            pipeline.process(object(), MagicMock(spec=ITarget))
        self.assertIn("Expected IProcessor", str(caught.exception))
        self.assertEqual(pipeline.calls, [])

    def test_a_facade_that_is_not_one_is_rejected_before_transform(self):
        pipeline = Doubler()
        with self.assertRaises(PipelineError) as caught:
            pipeline.process(MagicMock(spec=IProcessor), object())
        self.assertIn("Expected ITarget", str(caught.exception))
        self.assertEqual(pipeline.calls, [])

    def test_the_input_check_survives_optimised_mode(self):
        """`assert` is removed under python -O; the check must not depend on it."""
        code = textwrap.dedent(
            """
            import logging
            from unittest.mock import MagicMock
            from wattleflow.concrete.pipeline import GenericPipeline, PipelineError
            from wattleflow.core import ITarget

            class P(GenericPipeline):
                def transform(self, processor, facade, **kw):
                    return 1

            try:
                P(level=logging.CRITICAL).process(object(), MagicMock(spec=ITarget))
            except PipelineError:
                print("rejected")
            else:
                print("accepted")
            """
        )
        out = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "rejected", out.stderr[-300:])

    def test_one_exception_family(self):
        self.assertTrue(issubclass(PipelineError, PipelineException))


class LifecycleTest(unittest.TestCase):
    def collect(self, build):
        unraisable = []
        previous, sys.unraisablehook = sys.unraisablehook, unraisable.append
        try:
            try:
                build()
            except Exception:
                pass
            import gc

            gc.collect()
        finally:
            sys.unraisablehook = previous
        return unraisable

    def test_a_failed_construction_leaves_no_destructor_error(self):
        class Broken(Doubler):
            def __init__(self):
                raise RuntimeError("fails before the base is built")

        self.assertEqual(self.collect(Broken), [])

    def test_a_construction_that_fails_in_the_base_leaves_no_destructor_error(self):
        self.assertEqual(self.collect(lambda: Doubler(flag=1, level=object())), [])

    def test_an_unbuilt_object_answers_a_missing_name_with_that_name(self):
        bare = Doubler.__new__(Doubler)
        with self.assertRaises(AttributeError) as caught:
            _ = bare.anything
        self.assertIn("anything", str(caught.exception))

    def test_a_normal_object_is_discarded_without_error(self):
        def build():
            Doubler()

        self.assertEqual(self.collect(build), [])


if __name__ == "__main__":
    unittest.main()
