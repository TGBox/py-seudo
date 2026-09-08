"""Tests for EDIFACT tokenizer and serialization."""
import pytest
from py_seudo.edifact.tokenizer import (
    EdifactDelimiters,
    EdifactParser,
    EdifactSegment,
    serialize_segments,
)


def test_default_delimiters():
    raw = "UNB+UNOC:3+123+456'UNH+1+SLGA:15''"
    parser = EdifactParser(raw)
    assert parser.delimiters.element_sep == "+"
    assert parser.delimiters.component_sep == ":"
    assert parser.delimiters.release_char == "?"
    assert parser.delimiters.segment_terminator == "'"

    segments = parser.parse_segments()
    assert len(segments) == 2
    assert segments[0].tag == "UNB"
    assert segments[0].get_element(0, 0) == "UNOC"
    assert segments[0].get_element(0, 1) == "3"
    assert segments[0].get_element(1, 0) == "123"
    assert segments[0].get_element(2, 0) == "456"

    assert segments[1].tag == "UNH"
    assert segments[1].get_element(0, 0) == "1"
    assert segments[1].get_element(1, 0) == "SLGA"


def test_una_parsing():
    raw = "UNA:+.? 'UNB+UNOC:3+123+456'"
    parser = EdifactParser(raw)
    assert parser.delimiters.component_sep == ":"
    assert parser.delimiters.element_sep == "+"
    assert parser.delimiters.release_char == "?"
    assert parser.delimiters.segment_terminator == "'"

    segments = parser.parse_segments()
    assert len(segments) == 2
    assert segments[0].tag == "UNA"
    assert segments[1].tag == "UNB"

    # Re-serialization should preserve UNA
    reserialized = serialize_segments(segments)
    assert reserialized.startswith("UNA:+.? 'UNB+")


def test_escaped_delimiters():
    # '?' escapes '+', ':', and '\''
    raw = "NAD+VP+123+++Mustermann?+Sohn+Max?:Anton'"
    parser = EdifactParser(raw)
    segments = parser.parse_segments()
    assert len(segments) == 1
    seg = segments[0]
    assert seg.tag == "NAD"

    # Element 4 contains the escaped plus (after empty elements 2 and 3)
    assert seg.get_element(4, 0) == "Mustermann+Sohn"
    # Element 5 contains the escaped colon
    assert seg.get_element(5, 0) == "Max:Anton"

    # Reserializing should re-escape these characters
    res = seg.to_edifact()
    assert "?+" in res
    assert "?:" in res


def test_newlines_preservation():
    raw = "UNB+UNOC:3+1+2'\nUNH+1+TEST'\r\nUNT+2+1'\n"
    parser = EdifactParser(raw)
    segments = parser.parse_segments()
    assert len(segments) == 3
    assert segments[0].has_trailing_newline is True
    assert segments[1].has_trailing_newline is True
    assert segments[2].has_trailing_newline is True

    serialized = serialize_segments(segments)
    assert "\n" in serialized


def test_segment_get_set_element():
    seg = EdifactSegment(tag="TST")
    assert seg.get_element(0, 0) == ""
    assert seg.get_element(5, 5) == ""

    seg.set_element(0, "ABC", 0)
    assert seg.get_element(0, 0) == "ABC"

    seg.set_element(2, "XYZ", 1)
    assert seg.get_element(2, 1) == "XYZ"
    assert seg.get_element(2, 0) == ""
    assert seg.to_edifact() == "TST+ABC++:XYZ'"
