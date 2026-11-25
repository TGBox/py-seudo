from pathlib import Path

import pytest

from py_seudo.export_paths import is_synced_location, output_names, safe_stem


@pytest.mark.parametrize("name", ["ESOL0001", "SLLA_0042", "ESOL0099", "12345"])
def test_technical_names_are_kept(name):
    assert safe_stem(Path(f"{name}.txt"), "x") == name


@pytest.mark.parametrize(
    "name", ["Rueckweisung Meier Anna", "AW_ Ablehnung Mustermann", "demo_ESOL0001", "Meier"]
)
def test_other_names_are_replaced(name):
    assert safe_stem(Path(f"{name}.eml"), "fallback") == "fallback"


def test_output_names_never_contain_input_names():
    names = output_names(Path("Abrechnung Meier.txt"), Path("AW Rueckweisung Anna Meier.eml"))
    assert all("Meier" not in n for n in names.values())
    assert names["email"] == "rueckmeldung_anonymisiert.eml"
    assert names["report"].endswith("_summary_and_email_en.txt")


def test_output_names_keep_esol_id():
    names = output_names(Path("ESOL0001"), None)
    assert names["esol"] == "ESOL0001_anonymisiert"
    assert names["report"] == "ESOL0001_anonymisiert_summary_and_email_en.txt"


@pytest.mark.parametrize(
    "path, synced",
    [
        (r"C:\Users\x\OneDrive - Carasent\Export", True),
        (r"C:\Users\x\Dropbox\a", True),
        (r"\\fileserver\share\export", True),
        (r"C:\Users\x\Documents\Export", False),
        ("/home/x/export", False),
    ],
)
def test_sync_detection(path, synced):
    assert is_synced_location(Path(path)) is synced
