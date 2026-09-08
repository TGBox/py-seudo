"""Additional tests to maximize test coverage across edge cases and helper methods."""
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

from py_seudo.edifact.anonymizer import EsolAnonymizer
from py_seudo.email.anonymizer import EmailAnonymizer
from py_seudo.engine import PseudoEngine
from py_seudo.gui.app import MainWindow
from py_seudo.models import AnonymizationResult, MappingEntry, ReplacementCategory


def test_models_category_grouping():
    result = AnonymizationResult()
    m1 = MappingEntry("KV1", "X1", ReplacementCategory.KVNR)
    m2 = MappingEntry("KV2", "X2", ReplacementCategory.KVNR)
    m3 = MappingEntry("Dr. A", "Dr. B", ReplacementCategory.DOCTOR_NAME)
    result.mappings = [m1, m2, m3]

    grouped = result.get_mappings_by_category()
    assert ReplacementCategory.KVNR.value in grouped
    assert len(grouped[ReplacementCategory.KVNR.value]) == 2
    assert ReplacementCategory.DOCTOR_NAME.value in grouped
    assert len(grouped[ReplacementCategory.DOCTOR_NAME.value]) == 1


def test_multipart_email_anonymization():
    raw_multipart = (
        "From: Kasse <info@kasse.de>\n"
        "To: Praxis <team@praxis.de>\n"
        "Subject: Pruefprotokoll\n"
        "MIME-Version: 1.0\n"
        "Content-Type: multipart/alternative; boundary=\"boundary123\"\n"
        "\n"
        "--boundary123\n"
        "Content-Type: text/plain; charset=\"utf-8\"\n"
        "\n"
        "Fehler bei Patient Max Mustermann mit KVNR A123456789.\n"
        "--boundary123\n"
        "Content-Type: text/html; charset=\"utf-8\"\n"
        "\n"
        "<p>Fehler bei Patient Max Mustermann mit KVNR A123456789.</p>\n"
        "--boundary123--\n"
    )

    shared_mappings = {
        "Max Mustermann": MappingEntry("Max Mustermann", "Max_1 Mustermann_1", ReplacementCategory.PATIENT_NAME),
        "A123456789": MappingEntry("A123456789", "X000000001", ReplacementCategory.KVNR),
    }

    anon = EmailAnonymizer(raw_multipart, shared_mappings=shared_mappings)
    out_text, mappings = anon.anonymize()

    assert "Max Mustermann" not in out_text
    assert "A123456789" not in out_text
    assert "X000000001" in out_text


def test_additional_edifact_segments_and_qualifiers():
    raw = (
        "UNH+1+SLLA:15:0:0'\n"
        "INV+RE12345+00+20240101'\n"
        "NAD+LE+123456789+++Praxis Nord+Nordstr. 10+Kiel++24103+DE'\n"
        "NAD+IM+B987654321+++Meier+Hans+Suedring 4+Kiel++24105+DE'\n"
        "DTM+102:19951230:102'\n"
        "UNT+5+1'\n"
    )
    anon = EsolAnonymizer(raw)
    out_text, mappings = anon.anonymize()

    assert "RE12345" not in out_text
    assert "123456789" not in out_text
    assert "B987654321" not in out_text
    assert "Meier" not in out_text
    assert "Hans" not in out_text
    assert "19951230" not in out_text
    assert "19950615" in out_text


def test_file_save_methods(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window._load_demo_data()
    window._run_anonymization()

    assert window.current_result is not None

    # Simulate directory export directly
    dest = tmp_path / "export_dir"
    dest.mkdir(parents=True, exist_ok=True)
    p_esol = dest / "ESOL_anonymisiert.txt"
    p_mail = dest / "rueckmeldung_anonymisiert.eml"

    p_esol.write_text(window.current_result.anonymized_esol, encoding="utf-8")
    p_mail.write_text(window.current_result.anonymized_email, encoding="utf-8")

    assert p_esol.exists()
    assert p_mail.exists()
    assert "123456789" not in p_esol.read_text(encoding="utf-8")
    assert "A123456789" not in p_mail.read_text(encoding="utf-8")


def test_file_drop_box_load_file(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    sample_file = tmp_path / "test_input.txt"
    sample_file.write_text("Test content", encoding="utf-8")

    window.esol_box.load_file(sample_file)
    assert window.esol_box.file_path == sample_file
    assert window.esol_box.file_content == "Test content"
    assert window.esol_box.clear_btn.isEnabled() is True

    window.esol_box.clear()
    assert window.esol_box.file_path is None
    assert window.esol_box.file_content == ""
    assert window.esol_box.clear_btn.isEnabled() is False


def test_main_entrypoint(monkeypatch):
    import py_seudo.main as main_mod
    from PySide6.QtWidgets import QApplication

    # Mock app.exec to exit immediately
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    exit_code = main_mod.main()
    assert exit_code == 0
