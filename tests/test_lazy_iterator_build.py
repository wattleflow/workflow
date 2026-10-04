# Module name: tests/test_lazy_iterator_build.py
# Tests for the build step of LazyIterator (FRQ-ITR, DEF-ITR-03, DEF-ITR-04): the source is audited as
# Event.Create (Started, Completed or Failed) and its type is checked with Attribute.evaluate.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_lazy_iterator_build -v
import asyncio
import logging
import unittest

from wattleflow.concrete.exception import AttributeException
from wattleflow.concrete.iterator import LazyAsyncIterator, LazyIterator


class Good(LazyIterator):
    def create_iterator(self):
        return iter([1, 2])


class NotAnIterator(LazyIterator):
    def create_iterator(self):
        return [1, 2]


class Down(LazyIterator):
    def create_iterator(self):
        raise RuntimeError("source down")


def audit(case, iterator_class, fetches=1):
    iterator = iterator_class()
    with case.assertLogs(level=logging.DEBUG) as logged:
        for _ in range(fetches):
            try:
                next(iterator)
            except Exception:
                pass
    return "\n".join(logged.output)


class BuildAuditTest(unittest.TestCase):
    def test_a_successful_build_is_audited_as_started_then_completed(self):
        text = audit(self, Good)
        self.assertIn("Create", text)
        self.assertLess(text.index("Started"), text.index("Completed"))
        self.assertNotIn("Failed", text)

    def test_a_failed_build_is_audited_with_the_reason(self):
        text = audit(self, Down)
        self.assertIn("Failed", text)
        self.assertIn("source down", text)

    def test_only_the_first_fetch_is_audited(self):
        text = audit(self, Good, fetches=2)
        self.assertEqual(text.count("Completed"), 1)


class SourceTypeTest(unittest.TestCase):
    def test_a_source_that_is_not_an_iterator_is_rejected_at_build(self):
        with self.assertRaises(AttributeException):
            next(NotAnIterator())

    def test_a_rejected_source_is_not_kept(self):
        iterator = NotAnIterator()
        with self.assertRaises(AttributeException):
            next(iterator)
        self.assertIsNone(iterator._iterator)

    def test_a_generator_is_accepted(self):
        class Gen(LazyIterator):
            def create_iterator(self):
                yield from (1, 2)

        self.assertEqual(list(Gen()), [1, 2])


class AsyncGood(LazyAsyncIterator):
    def create_iterator(self):
        async def items():
            yield 1

        return items()


class AsyncSync(LazyAsyncIterator):
    def create_iterator(self):
        return iter([1, 2])


class AsyncDown(LazyAsyncIterator):
    def create_iterator(self):
        raise RuntimeError("source down")


class AsyncBuildTest(unittest.TestCase):
    def fetch(self, iterator_class):
        async def run():
            return await iterator_class().__anext__()

        with self.assertLogs(level=logging.DEBUG) as logged:
            try:
                asyncio.run(run())
            except Exception as error:
                return error, "\n".join(logged.output)
        return None, "\n".join(logged.output)

    def test_a_synchronous_source_is_rejected_with_the_framework_exception(self):
        error, _ = self.fetch(AsyncSync)
        self.assertIsInstance(error, AttributeException)

    def test_a_rejected_source_is_not_kept(self):
        iterator = AsyncSync()
        with self.assertRaises(AttributeException):
            asyncio.run(iterator.__anext__())
        self.assertIsNone(iterator._iterator)

    def test_a_successful_build_is_audited(self):
        _, text = self.fetch(AsyncGood)
        self.assertLess(text.index("Started"), text.index("Completed"))

    def test_a_failed_build_is_audited_with_the_reason(self):
        _, text = self.fetch(AsyncDown)
        self.assertIn("Failed", text)
        self.assertIn("source down", text)


if __name__ == "__main__":
    unittest.main()
