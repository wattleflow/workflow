# Module name: tests/test_serialisation.py
# Tests for GenericParser, GenericFormatter and GenericConverter (FRQ-SER-PAR, FRQ-SER-FMT,
# FRQ-SER-CNV): one declared source per parse, sources checked for what they are, a formatter that
# answers bytes or str, every failure carried as the layer's own error with its cause, and a
# converter that runs its strategy as the strategy's caller.
#
# Run from `workflow/`:
#   PYTHONPATH=src:../core/src python -m unittest tests.test_serialisation -v
import os
import tempfile
import unittest
from io import BytesIO

from wattleflow.concrete.serialisation import (
    ConverterError,
    FormatterError,
    GenericConverter,
    GenericFormatter,
    GenericParser,
    ParserError,
)
from wattleflow.core import IStrategy


class Echo(GenericParser):
    """Records what it was handed."""

    def __init__(self):
        self.seen = {}

    def deserialise(self, reader, **kwargs):
        self.seen = {"reader": reader, "kwargs": dict(kwargs)}
        return reader.read()


class Text(Echo):
    def deserialise(self, reader, **kwargs):
        return self.decode(reader, **kwargs)


class Failing(GenericParser):
    def deserialise(self, reader, **kwargs):
        raise ValueError("bad bytes")


class OwnError(Exception):
    def __init__(self, caller=None, error=""):
        super().__init__(error)


class Passing(GenericParser):
    ERROR = OwnError
    ERRORS = (OwnError, KeyError)

    def deserialise(self, reader, **kwargs):
        raise KeyError("own family")


class ParserSourceTest(unittest.TestCase):
    def test_exactly_one_source_is_required(self):
        parser = Echo()
        for kwargs in ({}, {"payload": b"x", "stream": BytesIO(b"y")}):
            with self.subTest(kwargs=sorted(kwargs)), self.assertRaises(ParserError) as caught:
                parser.parse(**kwargs)
            self.assertIn("exactly one", str(caught.exception))

    def test_a_stream_is_borrowed_and_not_closed(self):
        stream = BytesIO(b"abc")
        parser = Echo()
        self.assertEqual(parser.parse(stream=stream), b"abc")
        self.assertFalse(stream.closed)

    def test_a_path_is_opened_and_closed_by_the_base(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"from disk")
        try:
            parser = Echo()
            self.assertEqual(parser.parse(path=handle.name), b"from disk")
            self.assertTrue(parser.seen["reader"].closed)
        finally:
            os.unlink(handle.name)

    def test_a_payload_is_read_from_memory(self):
        self.assertEqual(Echo().parse(payload=b"abc"), b"abc")

    def test_the_source_keyword_is_consumed_and_options_are_forwarded(self):
        parser = Echo()
        parser.parse(payload=b"x", sep=";")
        self.assertEqual(parser.seen["kwargs"], {"sep": ";"})

    def test_a_missing_file_is_a_parser_error_with_its_cause(self):
        with self.assertRaises(ParserError) as caught:
            Echo().parse(path="/no/such/file")
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

    def test_a_payload_that_is_not_bytes_is_refused(self):
        for bad in (None, "text", 5, ["a"]):
            with self.subTest(bad=bad), self.assertRaises(ParserError):
                Echo().parse(payload=bad)

    def test_a_bytes_like_payload_is_accepted(self):
        self.assertEqual(Echo().parse(payload=bytearray(b"abc")), b"abc")
        self.assertEqual(Echo().parse(payload=memoryview(b"abc")), b"abc")

    def test_a_stream_without_read_is_refused(self):
        for bad in (None, "text", 5):
            with self.subTest(bad=bad), self.assertRaises(ParserError):
                Echo().parse(stream=bad)

    def test_a_path_must_be_a_string_or_a_path(self):
        for bad in (None, 5, b"bytes"):
            with self.subTest(bad=bad), self.assertRaises(ParserError):
                Echo().parse(path=bad)

    def test_an_integer_path_is_not_taken_for_a_file_descriptor(self):
        fd = os.open(os.devnull, os.O_RDONLY)
        try:
            with self.assertRaises(ParserError):
                Echo().parse(path=fd)
            os.fstat(fd)  # still open: the base did not adopt and close it
        finally:
            os.close(fd)


class ParserFailureTest(unittest.TestCase):
    def test_a_failure_in_deserialise_is_a_parser_error_with_its_cause(self):
        with self.assertRaises(ParserError) as caught:
            Failing().parse(payload=b"x")
        self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertIn("Failing.parse error: bad bytes", str(caught.exception))

    def test_an_exception_of_the_layers_own_family_passes_unchanged(self):
        with self.assertRaises(KeyError):
            Passing().parse(payload=b"x")

    def test_a_specialisation_outside_the_root_declares_its_own_error(self):
        class Other(Failing):
            ERROR = OwnError
            ERRORS = (OwnError,)

        with self.assertRaises(OwnError):
            Other().parse(payload=b"x")

    def test_deserialise_is_abstract(self):
        class NoBody(GenericParser):
            pass

        with self.assertRaises(TypeError):
            NoBody()


class DecodeTest(unittest.TestCase):
    def test_the_default_encoding_is_utf8(self):
        self.assertEqual(Text().parse(payload="čšž".encode("utf-8")), "čšž")

    def test_the_call_overrides_the_class_and_the_class_the_default(self):
        class Latin(Text):
            ENCODING = "latin-1"

        data = "é".encode("latin-1")
        self.assertEqual(Latin().parse(payload=data), "é")
        with self.assertRaises(ParserError):
            Latin().parse(payload=data, encoding="utf-8")

    def test_undecodable_bytes_are_a_parser_error(self):
        with self.assertRaises(ParserError):
            Text().parse(payload=b"\xff\xfe\xfa")


class Upper(GenericFormatter):
    SUFFIX = ".txt"

    def serialise(self, content, **kwargs):
        return str(content).upper()


class Typed(Upper):
    CONTENT = dict

    def serialise(self, content, **kwargs):
        return b"typed"


class FormatterTest(unittest.TestCase):
    def test_content_is_mandatory(self):
        with self.assertRaises(FormatterError) as caught:
            Upper().render()
        self.assertIn("content", str(caught.exception))

    def test_render_returns_the_payload(self):
        self.assertEqual(Upper().render(content="abc"), "ABC")

    def test_a_format_without_a_declared_type_takes_anything(self):
        self.assertEqual(Upper().render(content=None), "NONE")

    def test_a_declared_type_is_enforced(self):
        self.assertEqual(Typed().render(content={}), b"typed")
        for bad in (None, [], "text"):
            with self.subTest(bad=bad), self.assertRaises(FormatterError):
                Typed().render(content=bad)

    def test_a_failure_in_serialise_is_a_formatter_error_with_its_cause(self):
        class Boom(Upper):
            def serialise(self, content, **kwargs):
                raise ValueError("cannot")

        with self.assertRaises(FormatterError) as caught:
            Boom().render(content=1)
        self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertIn("Boom.render error: cannot", str(caught.exception))

    def test_an_exception_of_the_layers_own_family_passes_unchanged(self):
        class Own(Upper):
            ERROR = OwnError
            ERRORS = (OwnError,)

            def serialise(self, content, **kwargs):
                raise OwnError(error="own")

        with self.assertRaises(OwnError):
            Own().render(content=1)

    def test_a_payload_that_is_neither_bytes_nor_text_is_refused(self):
        def wrong(value):
            class Wrong(Upper):
                def serialise(self, content, **kwargs):
                    return value

            return Wrong()

        for bad in (None, 5, ["a"]):
            with self.subTest(bad=bad), self.assertRaises(FormatterError):
                wrong(bad).render(content=1)

    def test_bytearray_and_memoryview_are_payloads(self):
        class Raw(Upper):
            def serialise(self, content, **kwargs):
                return bytearray(b"ab")

        self.assertEqual(Raw().render(content=1), bytearray(b"ab"))

    def test_options_reach_serialise_and_content_does_not_repeat(self):
        seen = {}

        class Spy(Upper):
            def serialise(self, content, **kwargs):
                seen.update(kwargs)
                return "x"

        Spy().render(content=1, indent=2)
        self.assertEqual(seen, {"indent": 2})


class StreamTest(unittest.TestCase):
    def test_stream_writes_text_in_the_encoding_of_the_call(self):
        handle = BytesIO()
        Upper().stream(handle, "é", encoding="latin-1")
        self.assertEqual(handle.getvalue(), "É".encode("latin-1"))

    def test_the_class_encoding_is_the_default(self):
        class Latin(Upper):
            ENCODING = "latin-1"

        handle = BytesIO()
        Latin().stream(handle, "é")
        self.assertEqual(handle.getvalue(), "É".encode("latin-1"))

    def test_bytes_are_written_as_they_are(self):
        handle = BytesIO()
        Typed().stream(handle, {})
        self.assertEqual(handle.getvalue(), b"typed")

    def test_an_unencodable_text_is_a_formatter_error_not_a_raw_error(self):
        with self.assertRaises(FormatterError):
            Upper().stream(BytesIO(), "č", encoding="ascii")

    def test_a_failing_sink_is_a_formatter_error(self):
        class Closed(BytesIO):
            def write(self, data):
                raise OSError("sink down")

        with self.assertRaises(FormatterError) as caught:
            Upper().stream(Closed(), "x")
        self.assertIsInstance(caught.exception.__cause__, OSError)


class Plus(IStrategy):
    def __init__(self, fail=None):
        self.fail, self.calls = fail, []

    @property
    def name(self):
        return "Plus"

    def execute(self, caller, **kwargs):
        self.calls.append((caller, kwargs))
        if self.fail:
            raise self.fail
        return kwargs["source"] + 1


class Adder(GenericConverter):
    pass


class ConverterTest(unittest.TestCase):
    def test_convert_runs_the_strategy_with_the_converter_as_its_caller(self):
        strategy, converter = Plus(), Adder(Plus())
        converter.set_strategy(strategy)
        self.assertEqual(converter.convert(1, step=2), 2)
        caller, kwargs = strategy.calls[0]
        self.assertIs(caller, converter)
        self.assertEqual(kwargs, {"source": 1, "step": 2})

    def test_without_a_strategy_it_is_a_converter_error(self):
        with self.assertRaises(ConverterError):
            Adder().convert(1)

    def test_a_strategy_of_the_wrong_type_is_refused(self):
        class Narrow(GenericConverter):
            STRATEGY = Plus

        class Other(IStrategy):
            name = "Other"

            def execute(self, caller, **kwargs):
                return None

        for converter, bad in ((Adder(), object()), (Narrow(), Other())):
            with self.subTest(bad=type(bad).__name__), self.assertRaises(ConverterError):
                converter.set_strategy(bad)

    def test_a_failure_in_the_strategy_is_a_converter_error_with_its_cause(self):
        converter = Adder(Plus(fail=ValueError("no")))
        with self.assertRaises(ConverterError) as caught:
            converter.convert(1)
        self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertIn("Adder.convert error: no", str(caught.exception))

    def test_an_exception_of_the_layers_own_family_passes_unchanged(self):
        own = ConverterError(caller=None, error="own")
        with self.assertRaises(ConverterError) as caught:
            Adder(Plus(fail=own)).convert(1)
        self.assertIs(caught.exception, own)

    def test_the_strategy_property_and_the_constructor_argument(self):
        strategy = Plus()
        self.assertIs(Adder(strategy).strategy, strategy)
        self.assertIsNone(Adder().strategy)

    def test_the_constructor_continues_the_cooperative_chain(self):
        calls = []

        class Tail:
            def __init__(self):
                calls.append("tail")

        class Combined(GenericConverter, Tail):
            pass

        Combined()
        self.assertEqual(calls, ["tail"])


class SlotsTest(unittest.TestCase):
    def test_the_light_bases_declare_empty_slots(self):
        for cls in (GenericParser, GenericFormatter, GenericConverter):
            with self.subTest(cls=cls.__name__):
                self.assertEqual(cls.__slots__, ())


if __name__ == "__main__":
    unittest.main()
