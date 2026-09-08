"""Main Application Window for py-seudo with Light/Dark mode, drag & drop, and tabs."""
from __future__ import annotations
from py_seudo.models import MappingEntry

from pathlib import Path
from typing import Optional

from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
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
from py_seudo.gui.english_tab import EnglishTabWidget
from py_seudo.gui.mapping_widget import MappingWidget
from py_seudo.gui.theme import DARK_THEME, LIGHT_THEME
from py_seudo.models import AnonymizationResult
from py_seudo.samples import (
    SAMPLE_EMAIL,
    SAMPLE_EMAIL_REJECTION,
    SAMPLE_ESOL,
    SAMPLE_ESOL_WITH_ERRORS,
)


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
        self.clear_btn.setObjectName("ClearButton")
        self.clear_btn.setToolTip("Datei entfernen")
        self.clear_btn.setFixedSize(32, 30)
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

        # Demo Data with Errors Button
        self.demo_errors_btn = QPushButton("⚠️ Demo mit Fehlern")
        self.demo_errors_btn.setToolTip("Lädt Testabrechnung mit fehlerhafter IK, KVNR und Belegnummer zur Fehler-Spiegelung")
        self.demo_errors_btn.clicked.connect(self._load_demo_errors)
        header.addWidget(self.demo_errors_btn)

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
        self.mapping_widget.mapping_updated.connect(self._on_mapping_updated)
        self.mapping_widget.mapping_added.connect(self._on_mapping_added)
        self.tabs.addTab(self.mapping_widget, "🔍 Ersetzungs-Protokoll & Mappings")

        # Tab 4: English Developer Report & Translation
        self.english_tab = EnglishTabWidget()
        self.english_tab.report_edited.connect(self._on_english_report_edited)
        self.tabs.addTab(self.english_tab, "🇬🇧 Englisch (Summary & E-Mail)")

        # Connect text_edited signals from diff previews
        self.esol_diff.text_edited.connect(self._on_esol_text_edited)
        self.email_diff.text_edited.connect(self._on_email_text_edited)

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

    def _load_demo_errors(self) -> None:
        self.esol_box.set_direct_text("demo_ESOL0099_fehler.txt", SAMPLE_ESOL_WITH_ERRORS)
        self.email_box.set_direct_text("demo_rueckweisung_email.eml", SAMPLE_EMAIL_REJECTION)
        self.status_bar.showMessage("Beispieldaten mit Abrechnungsfehlern geladen. Klicke auf 'Anonymisieren & Prüfen'!")

    def _reset_all(self) -> None:
        self.esol_box.clear()
        self.email_box.clear()
        self.ik_override_input.clear()
        self.esol_diff.set_content("", "")
        self.email_diff.set_content("", "")
        self.mapping_widget.set_mappings(AnonymizationResult())
        self.english_tab.set_result(None)
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
            self.english_tab.set_result(result)

            self.save_files_btn.setEnabled(True)

            total = result.total_replacements
            unique = len(result.mappings)
            base = (
                f"Anonymisierung abgeschlossen: {unique} eindeutige Entitäten "
                f"pseudonymisiert ({total} Gesamtersetzungen)."
            )
            if result.suspicions:
                # Nicht als Erfolg melden, solange etwas offen ist -- und den
                # Anwender direkt dorthin schicken, wo die Funde stehen.
                self.status_bar.showMessage(
                    f"⚠️ {base} {len(result.suspicions)} Stelle(n) konnten nicht sicher "
                    f"zugeordnet werden – siehe Reiter 'Ersetzungs-Protokoll'."
                )
                self.tabs.setCurrentWidget(self.mapping_widget)
            else:
                self.status_bar.showMessage(f"✓ {base}")

        except Exception as e:
            QMessageBox.critical(self, "Fehler bei der Anonymisierung", f"Fehler aufgetreten:\n{e}")

    def _on_esol_text_edited(self, text: str) -> None:
        if self.current_result:
            self.current_result.anonymized_esol = text
            self.status_bar.showMessage("✏️ ESOL-Abrechnungsdatei manuell im Editor geändert.")

    def _on_email_text_edited(self, text: str) -> None:
        if self.current_result:
            self.current_result.anonymized_email = text
            self.status_bar.showMessage("✏️ Rückmeldungsemail manuell im Editor geändert.")

    def _on_english_report_edited(self, text: str) -> None:
        if self.current_result:
            self.current_result.english_report = text
            self.status_bar.showMessage("✏️ Englischer Report manuell im Editor geändert.")

    def _on_mapping_updated(self, original: str, old_pseudo: str, new_pseudo: str) -> None:
        """Propagate updated pseudonym from the mapping table to both preview widgets."""
        if not self.current_result:
            return

        c_esol = self.esol_diff.replace_text_globally(old_pseudo, new_pseudo)
        c_mail = self.email_diff.replace_text_globally(old_pseudo, new_pseudo)
        self.current_result.anonymized_esol = self.esol_diff.get_anonymized_text()
        self.current_result.anonymized_email = self.email_diff.get_anonymized_text()

        total = c_esol + c_mail
        self.english_tab.set_result(self.current_result)
        self.status_bar.showMessage(
            f"✓ Pseudonym manuell geändert: '{old_pseudo}' → '{new_pseudo}' ({total} Vorkommen in Texten aktualisiert)."
        )

    def _on_mapping_added(self, entry: MappingEntry) -> None:
        """Apply newly added custom replacement across preview widgets and register in result."""
        if not self.current_result:
            return

        c_esol = self.esol_diff.replace_text_globally(entry.original, entry.pseudonym)
        c_mail = self.email_diff.replace_text_globally(entry.original, entry.pseudonym)
        entry.count = max(1, c_esol + c_mail)

        self.current_result.anonymized_esol = self.esol_diff.get_anonymized_text()
        self.current_result.anonymized_email = self.email_diff.get_anonymized_text()
        self.current_result.mappings.append(entry)

        self.mapping_widget.set_mappings(self.current_result)
        self.english_tab.set_result(self.current_result)
        self.status_bar.showMessage(
            f"✓ Neue Ersetzung hinzugefügt: '{entry.original}' → '{entry.pseudonym}' ({entry.count} Ersetzungen)."
        )

    def _save_anonymized_files(self) -> None:
        if not self.current_result:
            return

        # Always read latest live text from the preview panes
        self.current_result.anonymized_esol = self.esol_diff.get_anonymized_text()
        self.current_result.anonymized_email = self.email_diff.get_anonymized_text()

        # Offene Verdachtsfaelle vor dem Export bestaetigen lassen. Wer die Datei
        # weitergibt, soll wissen, dass noch etwas ungeklaert ist.
        if self.current_result.suspicions:
            anzahl = len(self.current_result.suspicions)
            reply = QMessageBox.warning(
                self,
                "⚠️ Restrisiko vor dem Export",
                f"An {anzahl} Stelle(n) konnte py-seudo nicht sicher entscheiden, "
                f"ob ein Personenbezug vorliegt – diese wurden NICHT ersetzt.\n\n"
                f"Die Liste steht im Reiter 'Ersetzungs-Protokoll & Mappings'.\n\n"
                f"Trotzdem exportieren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
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

            # Export English Summary & Translation file if available
            self.current_result.english_report = self.english_tab.get_report_text()
            if self.current_result.english_report and self.current_result.english_report.strip():
                if self.esol_box.file_path:
                    base_stem = self.esol_box.file_path.stem
                elif self.email_box.file_path:
                    base_stem = self.email_box.file_path.stem
                else:
                    base_stem = "abrechnung"
                en_name = f"{base_stem}_anonymisiert_summary_and_email_en.txt"
                p_en = dest / en_name
                p_en.write_text(self.current_result.english_report, encoding="utf-8")
                saved_files.append(p_en.name)

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
