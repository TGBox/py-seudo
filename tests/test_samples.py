"""Tests validating the integrity of built-in sample data."""
from py_seudo.edifact.tokenizer import EdifactParser
from py_seudo.samples import SAMPLE_EMAIL, SAMPLE_ESOL


def test_sample_esol_structure():
    assert "UNA:+.? '" in SAMPLE_ESOL
    assert "UNB+UNOC:3" in SAMPLE_ESOL
    assert "SLGA:15" in SAMPLE_ESOL
    assert "SLLA:15" in SAMPLE_ESOL
    assert "DIA+M54.5" in SAMPLE_ESOL
    assert "ENF+21201" in SAMPLE_ESOL

    parser = EdifactParser(SAMPLE_ESOL)
    segments = parser.parse_segments()
    assert len(segments) >= 15
    tags = [s.tag for s in segments]
    assert "UNA" in tags
    assert "UNB" in tags
    assert "UNH" in tags
    assert "FKT" in tags
    assert "REC" in tags
    assert "NAD" in tags
    assert "DTM" in tags
    assert "DIA" in tags
    assert "ENF" in tags
    assert "UNT" in tags
    assert "UNZ" in tags


def test_sample_email_content():
    assert "From:" in SAMPLE_EMAIL
    assert "To:" in SAMPLE_EMAIL
    assert "A123456789" in SAMPLE_EMAIL
    assert "123456789" in SAMPLE_EMAIL
    assert "M54.5" in SAMPLE_EMAIL
    assert "21201" in SAMPLE_EMAIL
