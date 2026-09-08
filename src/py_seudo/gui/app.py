"""Main Application Window for py-seudo with Light/Dark mode, drag & drop, and tabs."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from py_seudo.engine import PseudoEngine
from py_seudo.gui.diff_widget import DiffWidget
from py_seudo.gui.mapping_widget import MappingWidget
from py_seudo.gui.theme import DARK_THEME, LIGHT_THEME
from py_seudo.models import AnonymizationResult
from py_seudo.samples import SAMPLE_EMAIL, SAMPLE_ESOL


class FileDropBox(QGroupBox):
    """File selection card with drag and drop support."""

    def __init__(self, title: str, file_filters: str, parent: QWidget | None = None):
        super().__init__(title, parent)
        self.file_filters = file_filters
        self.file_path: Optional[Path] = None
        self.file_content: str = ""
        self.setAcceptDrops(True)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 10)
        layout.setSpacing(8)

        self.path_label = QLabel("Keine Datei ausgewählt (Hierher ziehen oder durchsuchen)")
        self.path_label.setStyleSheet("color: #94a3b8; font-style: italic;")

        self.browse_btn = QPushButton("📁 Durchsuchen...")
        self.browse_btn.clicked.connect(self._browse)

        self.clear_btn = QPushButton("✕")
        self.clear_btn.setToolTip("Datei entfernen")
        self.clear_btn.setMaximumWidth(32)
        self.clear_btn.clicked.connect(self.clear)
        self.clear_btn.setEnabled(False)

        layout.addWidget(self.path_label, 1)
        layout.addWidget(self.browse_btn)
        layout.addWidget(self.clear_btn)

    def _browse(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"{self.title()} auswählen", "", self.file_filters
        )
        if file_path:
            self.load_file(Path(file_path))

    def load_file(self, path: Path) -> None:
        try:
            # Attempt utf-8 first, fallback to latin-1 (common in older German EDIFACT exports)
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="latin-1")

            self.file_path = path
            self.file_content = content
            self.path_label.setText(f"✓ {path.name} ({len(content)} Zeichen)")
            self.path_label.setStyleSheet("color: #10b981; font-weight: 500;")
            self.clear_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Lesen", f"Konnte Datei nicht öffnen:\n{e}")

    def set_direct_text(self, name: str, text: str) -> None:
        self.file_path = Path(name)
        self.file_content = text
        self.path_label.setText(f"✓ {name} (Demo-Datensatz, {len(text)} Zeichen)")
        self.path_label.setStyleSheet("color: #38bdf8; font-weight: 500;")
        self.clear_btn.setEnabled(True)

    def clear(self) -> None:
        self.file_path = None
        self.file_content = ""
        self.path_label.setText("Keine Datei ausgewählt (Hierher ziehen oder durchsuchen)")
        self.path_label.setStyleSheet("color: #94a3b8; font-style: italic;")
        self.clear_btn.setEnabled(False)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            if path.is_file():
                self.load_file(path)


class MainWindow(QMainWindow):
    """Main Application Window for py-seudo."""

    def __init__(self):
        super().__init__()
        self.is_dark_mode = True
        self.engine = PseudoEngine()
        self.current_result: Optional[AnonymizationResult] = None

        self.setWindowTitle("py-seudo – DSGVO-Abrechnungsanonymisierung (§ 302 SGB V)")
        self.resize(1200, 800)

        self._init_ui()
        self._apply_theme()

    def _init_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        # 1. Header Bar
        header = QHBoxLayout()
        header.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        app_title = QLabel("py-seudo")
        app_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #38bdf8;")
        app_subtitle = QLabel("DSGVO-konforme Pseudonymisierung von ESOL-Abrechnungen und Kassen-Rückmeldungen")
        app_subtitle.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_box.addWidget(app_title)
        title_box.addWidget(app_subtitle)
        header.addLayout(title_box)

        header.addStretch()

        # Demo Data Button
        self.demo_btn = QPushButton("📁 Beispieldaten laden")
        self.demo_btn.setToolTip("Lädt realistische § 302 Testabrechnung und Fehlere-Mail")
        self.demo_btn.clicked.connect(self._load_demo_data)
        header.addWidget(self.demo_btn)

        # Reset Button
        self.reset_btn = QPushButton("🔄 Zurücksetzen")
        self.reset_btn.clicked.connect(self._reset_all)
        header.addWidget(self.reset_btn)

        # Dark/Light Mode Toggle
        self.theme_btn = QPushButton("☀️ Light Mode")
        self.theme_btn.clicked.connect(self._toggle_theme)
        header.addWidget(self.theme_btn)

        main_layout.addLayout(header)

        # 2. File Selection Cards
        file_row = QHBoxLayout()
        file_row.setSpacing(12)

        self.esol_box = FileDropBox(
            "1. ESOL-Abrechnungsdatei (keine Endungseinschränkung)",
            "Alle Dateien (*);;Alle Dateien (*.*);;ESOL / EDIFACT Dateien (*.esol *.txt *.edi *.org)",
        )
        self.email_box = FileDropBox(
            "2. Rückmeldungsemail der Kasse",
            "E-Mail-Dateien (*.eml *.txt *.msg);;Alle Dateien (*.*)",
        )

        file_row.addWidget(self.esol_box, 1)
        file_row.addWidget(self.email_box, 1)
        main_layout.addLayout(file_row)

        # 3. Action and Options Bar
        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        # Optional Praxis-IK Override
        action_bar.addWidget(QLabel("Praxis-IK (optional):"))
        self.ik_override_input = QLineEdit()
        self.ik_override_input.setPlaceholderText("Wird automatisch erkannt")
        self.ik_override_input.setMaximumWidth(170)
        self.ik_override_input.setToolTip(
            "Falls leer, wird das Praxis-IK automatisch aus dem UNB/FKT-Segment ermittelt."
        )
        action_bar.addWidget(self.ik_override_input)

        action_bar.addSpacing(15)

        # Primary Anonymize Button
        self.anonymize_btn = QPushButton("✨ Anonymisieren")
        self.anonymize_btn.setObjectName("PrimaryButton")
        self.anonymize_btn.clicked.connect(self._run_anonymization)
        action_bar.addWidget(self.anonymize_btn)

        action_bar.addStretch()

        # Save Anonymized Files Button
        self.save_files_btn = QPushButton("💾 Anonymisierte Dateien speichern...")
        self.save_files_btn.setObjectName("SuccessButton")
        self.save_files_btn.setEnabled(False)
        self.save_files_btn.clicked.connect(self._save_anonymized_files)
        action_bar.addWidget(self.save_files_btn)

        main_layout.addLayout(action_bar)

        # 4. Results Tabs
        self.tabs = QTabWidget()

        # Tab 1: ESOL Diff
        self.esol_diff = DiffWidget("ESOL Abrechnungsdatei (§ 302 SGB V)")
        self.tabs.addTab(self.esol_diff, "📄 ESOL Abrechnungsdatei")

        # Tab 2: Email Diff
        self.email_diff = DiffWidget("Rückmeldungsemail der Krankenkasse")
        self.tabs.addTab(self.email_diff, "✉️ Rückmeldungsemail")

        # Tab 3: Mapping Inspector
        self.mapping_widget = MappingWidget()
        self.tabs.addTab(self.mapping_widget, "🔍 Ersetzungs-Protokoll & Mappings")

        main_layout.addWidget(self.tabs, 1)

        # 5. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit. Bitte ESOL-Datei und/oder Rückmeldungsemail auswählen.")

    def _toggle_theme(self) -> None:
        self.is_dark_mode = not self.is_dark_mode
        self._apply_theme()

    def _apply_theme(self) -> None:
        if self.is_dark_mode:
            self.setStyleSheet(DARK_THEME)
            self.theme_btn.setText("☀️ Light Mode")
        else:
            self.setStyleSheet(LIGHT_THEME)
            self.theme_btn.setText("🌙 Dark Mode")

    def _load_demo_data(self) -> None:
        self.esol_box.set_direct_text("demo_ESOL0001.txt", SAMPLE_ESOL)
        self.email_box.set_direct_text("demo_rueckmeldung.eml", SAMPLE_EMAIL)
        self.status_bar.showMessage("Realistische Beispieldaten geladen. Klicke auf 'Anonymisieren'!")

    def _reset_all(self) -> None:
        self.esol_box.clear()
        self.email_box.clear()
        self.ik_override_input.clear()
        self.esol_diff.set_content("", "")
        self.email_diff.set_content("", "")
        self.mapping_widget.set_mappings(AnonymizationResult())
        self.save_files_btn.setEnabled(False)
        self.current_result = None
        self.status_bar.showMessage("Zurückgesetzt. Bereit für neue Dateien.")

    def _run_anonymization(self) -> None:
        esol_text = self.esol_box.file_content
        email_text = self.email_box.file_content

        if not esol_text.strip() and not email_text.strip():
            QMessageBox.warning(
                self,
                "Keine Daten vorhanden",
                "Bitte wählen Sie mindestens eine ESOL-Datei oder eine Rückmeldungsemail aus,\n"
                "oder klicken Sie auf 'Beispieldaten laden'.",
            )
            return

        specified_ik = self.ik_override_input.text().strip() or None
        self.engine = PseudoEngine(specified_practice_ik=specified_ik)

        try:
            result = self.engine.process(esol_text=esol_text, email_text=email_text)
            self.current_result = result

            # Update tabs
            self.esol_diff.set_content(result.original_esol, result.anonymized_esol)
            self.email_diff.set_content(result.original_email, result.anonymized_email)
            self.mapping_widget.set_mappings(result)

            self.save_files_btn.setEnabled(True)

            total = result.total_replacements
            unique = len(result.mappings)
            self.status_bar.showMessage(
                f"✓ Anonymisierung erfolgreich: {unique} eindeutige Entitäten pseudonymisiert ({total} Gesamtersetzungen)."
            )

        except Exception as e:
            QMessageBox.critical(self, "Fehler bei der Anonymisierung", f"Fehler aufgetreten:\n{e}")

    def _save_anonymized_files(self) -> None:
        if not self.current_result:
            return

        target_dir = QFileDialog.getExistingDirectory(
            self, "Zielordner für anonymisierte Dateien auswählen"
        )
        if not target_dir:
            return

        dest = Path(target_dir)
        saved_files = []

        try:
            if self.current_result.anonymized_esol:
                if self.esol_box.file_path and not self.esol_box.file_path.suffix:
                    esol_name = f"{self.esol_box.file_path.name}_anonymisiert"
                else:
                    esol_name = (
                        f"{self.esol_box.file_path.stem}_anonymisiert{self.esol_box.file_path.suffix}"
                        if self.esol_box.file_path
                        else "ESOL0001_anonymisiert"
                    )
                p_esol = dest / esol_name
                try:
                    p_esol.write_text(self.current_result.anonymized_esol, encoding="latin-1")
                except UnicodeEncodeError:
                    p_esol.write_text(self.current_result.anonymized_esol, encoding="utf-8")
                saved_files.append(p_esol.name)

            if self.current_result.anonymized_email:
                email_ext = (
                    self.email_box.file_path.suffix if self.email_box.file_path else ".eml"
                )
                if not email_ext or email_ext.lower() not in (".eml", ".txt", ".msg"):
                    email_ext = ".eml"
                email_name = (
                    f"{self.email_box.file_path.stem}_anonymisiert{email_ext}"
                    if self.email_box.file_path
                    else f"rueckmeldung_anonymisiert{email_ext}"
                )
                p_mail = dest / email_name
                p_mail.write_text(self.current_result.anonymized_email, encoding="utf-8")
                saved_files.append(p_mail.name)

            QMessageBox.information(
                self,
                "Dateien gespeichert",
                f"Folgende anonymisierte Dateien wurden erfolgreich exportiert:\n\n"
                + "\n".join(f"• {f}" for f in saved_files)
                + f"\n\nIn den Ordner:\n{dest}",
            )
            self.status_bar.showMessage(f"✓ Dateien exportiert nach: {dest}")

        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Speichern", f"Konnte Dateien nicht schreiben:\n{e}")
