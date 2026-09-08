"""Robust EDIFACT tokenizer and segment serializer with UNA support."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class EdifactDelimiters:
    component_sep: str = ":"
    element_sep: str = "+"
    decimal_mark: str = "."
    release_char: str = "?"
    repetition_sep: str = " "
    segment_terminator: str = "'"


@dataclass
class EdifactSegment:
    tag: str
    elements: List[List[str]] = field(default_factory=list)
    has_trailing_newline: bool = False
    delimiters: EdifactDelimiters = field(default_factory=EdifactDelimiters)

    def get_element(self, element_index: int, component_index: int = 0) -> str:
        """Safely retrieve a component value from an element."""
        if 0 <= element_index < len(self.elements):
            elem = self.elements[element_index]
            if 0 <= component_index < len(elem):
                return elem[component_index]
        return ""

    def set_element(self, element_index: int, value: str, component_index: int = 0) -> None:
        """Safely set a component value in an element, expanding if necessary."""
        while len(self.elements) <= element_index:
            self.elements.append([""])
        elem = self.elements[element_index]
        while len(elem) <= component_index:
            elem.append("")
        elem[component_index] = value

    def to_edifact(self) -> str:
        """Serialize segment back to EDIFACT string."""
        # Special case: UNA segment has fixed layout without delimiters
        if self.tag == "UNA":
            d = self.delimiters
            una_str = f"UNA{d.component_sep}{d.element_sep}{d.decimal_mark}{d.release_char}{d.repetition_sep}{d.segment_terminator}"
            return una_str + ("\n" if self.has_trailing_newline else "")

        rel = self.delimiters.release_char
        elem_sep = self.delimiters.element_sep
        comp_sep = self.delimiters.component_sep
        term = self.delimiters.segment_terminator

        def escape_val(val: str) -> str:
            # Escape release char first, then delimiters
            out = []
            for ch in val:
                if ch in (rel, elem_sep, comp_sep, term):
                    out.append(rel + ch)
                else:
                    out.append(ch)
            return "".join(out)

        rendered_elements = []
        for elem in self.elements:
            rendered_comp = [escape_val(c) for c in elem]
            rendered_elements.append(comp_sep.join(rendered_comp))

        body = elem_sep.join([self.tag] + rendered_elements) if rendered_elements else self.tag
        result = body + term
        if self.has_trailing_newline:
            result += "\n"
        return result


class EdifactParser:
    """Parser and tokenizer for EDIFACT messages."""

    def __init__(self, raw_text: str):
        self.raw_text = raw_text
        self.delimiters = self._parse_delimiters()

    def _parse_delimiters(self) -> EdifactDelimiters:
        stripped = self.raw_text.lstrip()
        if stripped.startswith("UNA") and len(stripped) >= 9:
            return EdifactDelimiters(
                component_sep=stripped[3],
                element_sep=stripped[4],
                decimal_mark=stripped[5],
                release_char=stripped[6],
                repetition_sep=stripped[7],
                segment_terminator=stripped[8],
            )
        return EdifactDelimiters()

    def parse_segments(self) -> List[EdifactSegment]:
        """Tokenize text into list of EdifactSegment objects."""
        segments: List[EdifactSegment] = []
        text = self.raw_text
        idx = 0
        n = len(text)

        # Check for UNA segment
        stripped = text.lstrip()
        if stripped.startswith("UNA") and len(stripped) >= 9:
            una_end = text.find("UNA") + 9
            has_nl = una_end < n and text[una_end] in "\r\n"
            segments.append(
                EdifactSegment(
                    tag="UNA",
                    elements=[],
                    has_trailing_newline=has_nl,
                    delimiters=self.delimiters,
                )
            )
            # Skip past newline after UNA if present
            idx = una_end
            while idx < n and text[idx] in "\r\n":
                idx += 1

        rel = self.delimiters.release_char
        term = self.delimiters.segment_terminator

        while idx < n:
            # Skip leading whitespace/newlines between segments
            while idx < n and text[idx].isspace():
                idx += 1
            if idx >= n:
                break

            # Read until unescaped segment terminator
            seg_start = idx
            in_escape = False
            found_term = False

            while idx < n:
                ch = text[idx]
                if in_escape:
                    in_escape = False
                    idx += 1
                elif ch == rel:
                    in_escape = True
                    idx += 1
                elif ch == term:
                    found_term = True
                    idx += 1
                    break
                else:
                    idx += 1

            seg_content = text[seg_start : idx - 1 if found_term else idx]
            if not seg_content.strip():
                continue

            # Check if there is a trailing newline after this segment
            has_nl = False
            if idx < n and text[idx] in "\r\n":
                has_nl = True
                while idx < n and text[idx] in "\r\n":
                    idx += 1

            parsed_segment = self._parse_single_segment(seg_content, has_nl)
            segments.append(parsed_segment)

        return segments

    def _parse_single_segment(self, seg_content: str, has_nl: bool) -> EdifactSegment:
        elem_sep = self.delimiters.element_sep
        comp_sep = self.delimiters.component_sep
        rel = self.delimiters.release_char

        # Split elements by unescaped element_sep
        elements_raw: List[str] = []
        curr: List[str] = []
        in_escape = False

        for ch in seg_content:
            if in_escape:
                curr.append(rel)
                curr.append(ch)
                in_escape = False
            elif ch == rel:
                in_escape = True
            elif ch == elem_sep:
                elements_raw.append("".join(curr))
                curr = []
            else:
                curr.append(ch)
        if in_escape:
            curr.append(rel)
        elements_raw.append("".join(curr))

        if not elements_raw:
            return EdifactSegment(tag="", elements=[], has_trailing_newline=has_nl, delimiters=self.delimiters)

        tag = elements_raw[0]
        data_elements: List[List[str]] = []

        for elem_str in elements_raw[1:]:
            # Split element into components by unescaped comp_sep
            comps: List[str] = []
            comp_curr: List[str] = []
            in_escape_c = False
            for ch in elem_str:
                if in_escape_c:
                    comp_curr.append(ch)
                    in_escape_c = False
                elif ch == rel:
                    in_escape_c = True
                elif ch == comp_sep:
                    comps.append("".join(comp_curr))
                    comp_curr = []
                else:
                    comp_curr.append(ch)
            comps.append("".join(comp_curr))
            data_elements.append(comps)

        return EdifactSegment(
            tag=tag,
            elements=data_elements,
            has_trailing_newline=has_nl,
            delimiters=self.delimiters,
        )


def serialize_segments(segments: List[EdifactSegment]) -> str:
    """Serialize list of EdifactSegment back to full EDIFACT document string."""
    return "".join(s.to_edifact() for s in segments)
