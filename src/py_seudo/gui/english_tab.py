"""English Summary & Translation preview tab for py-seudo."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from py_seudo.gui.api_settings_dialog import ApiSettingsDialog
from py_seudo.models import AnonymizationResult
from py_seudo.translation.api_client import generate_developer_report
from py_seudo.translation.models import TranslationProvider, TranslationSettings
from py_seudo.translation.settings_manager import SettingsManager


class EnglishTabWidget(QWidget):
    """Tab displaying English issue summary and email translation with manual editing."""

    report_edited = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings: TranslationSettings = SettingsManager.load_settings()
        self.current_result: Optional[AnonymizationResult] = None
        self.is_dark_mode = True
        self._init_ui()

    def update_theme(self, is_dark: bool) -> None:
        self.is_dark_mode = is_dark
        self._update_status_badge()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Toolbar Card
        toolbar_card = QGroupBox("🇬🇧 Konfiguration & Anbieter für englischen Report")
        toolbar_layout = QHBoxLayout(toolbar_card)
        toolbar_layout.setContentsMargins(12, 10, 12, 10)
        toolbar_layout.setSpacing(10)

        toolbar_layout.addWidget(QLabel("Anbieter:"))

        self.provider_combo = QComboBox()
        self.provider_combo.setView(QListView())
        self.provider_combo.addItem("Lokaler Generator (Offline, DSGVO-konform)", TranslationProvider.LOCAL)
        self.provider_combo.addItem("OpenAI / Kompatibel (GPT-4o, Ollama)", TranslationProvider.OPENAI)
        self.provider_combo.addItem("Google Gemini", TranslationProvider.GEMINI)
        self.provider_combo.addItem("Anthropic Claude", TranslationProvider.CLAUDE)

        # Select provider from settings
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == self.settings.provider:
                self.provider_combo.setCurrentIndex(i)
                break
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        toolbar_layout.addWidget(self.provider_combo)

        self.settings_btn = QPushButton("⚙️ API-Einstellungen...")
        self.settings_btn.clicked.connect(self._open_settings)
        toolbar_layout.addWidget(self.settings_btn)

        self.regenerate_btn = QPushButton("🔄 Neu generieren")
        self.regenerate_btn.clicked.connect(self.regenerate)
        toolbar_layout.addWidget(self.regenerate_btn)

        toolbar_layout.addStretch()

        self.status_badge = QLabel("✓ Lokaler Generator (Offline)")
        self.status_badge.setObjectName("StatusBadge")
        toolbar_layout.addWidget(self.status_badge)
        self._update_status_badge()

        edit_badge = QLabel("✏️ Manuell bearbeitbar")
        edit_badge.setObjectName("EditBadge")
        toolbar_layout.addWidget(edit_badge)

        layout.addWidget(toolbar_card)

        # Text Editor
        self.editor = QPlainTextEdit()
        font = QFont("Consolas" if "Consolas" in QFont().families() else "Courier New", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        self.editor.setPlaceholderText(
            "Der englische Bericht (Problem-Zusammenfassung, EDIFACT-Segmentanalyse und E-Mail-Übersetzung) "
            "wird hier angezeigt, sobald Sie eine Abrechnungsdatei oder E-Mail anonymisieren."
        )
        self.editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.editor, 1)

        # Bottom Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.stats_label = QLabel("0 Zeichen | 0 Zeilen")
        self.stats_label.setObjectName("MutedLabel")
        bottom_bar.addWidget(self.stats_label)

        bottom_bar.addStretch()

        self.copy_btn = QPushButton("📋 In Zwischenablage kopieren")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        bottom_bar.addWidget(self.copy_btn)

        self.save_single_btn = QPushButton("💾 Nur diesen Report exportieren...")
        self.save_single_btn.clicked.connect(self._save_single_report)
        bottom_bar.addWidget(self.save_single_btn)

        layout.addLayout(bottom_bar)

    def _on_provider_changed(self) -> None:
        selected = self.provider_combo.currentData()
        if isinstance(selected, str):
            try:
                selected = TranslationProvider(selected)
            except ValueError:
                pass
        if isinstance(selected, TranslationProvider):
            self.settings.provider = selected
            SettingsManager.save_settings(self.settings)
            self._update_status_badge()

    def _update_status_badge(self) -> None:
        p = self.settings.provider
        if self.is_dark_mode:
            if p == TranslationProvider.LOCAL:
                self.status_badge.setText("✓ Lokaler Generator (Offline)")
                self.status_badge.setStyleSheet(
                    "background-color: #064e3b; color: #34d399; font-weight: bold; "
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #059669;"
                )
            elif p == TranslationProvider.OPENAI:
                model = self.settings.openai_model or "gpt-4o-mini"
                self.status_badge.setText(f"🌐 OpenAI ({model})")
                self.status_badge.setStyleSheet(
                    "background-color: #1e3a8a; color: #93c5fd; font-weight: bold; "
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #2563eb;"
                )
            elif p == TranslationProvider.GEMINI:
                model = self.settings.gemini_model or "gemini-1.5-flash"
                self.status_badge.setText(f"🌐 Gemini ({model})")
                self.status_badge.setStyleSheet(
                    "background-color: #1e3a8a; color: #93c5fd; font-weight: bold; "
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #2563eb;"
                )
            elif p == TranslationProvider.CLAUDE:
                model = self.settings.claude_model or "claude-3-5-haiku"
                self.status_badge.setText(f"🌐 Claude ({model})")
                self.status_badge.setStyleSheet(
                    "background-color: #581c87; color: #d8b4fe; font-weight: bold; "
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #7e22ce;"
                )
        else:
            if p == TranslationProvider.LOCAL:
                self.status_badge.setText("✓ Lokaler Generator (Offline)")
                self.status_badge.setStyleSheet(
                    "background-color: #ecfdf5; color: #065f46; font-weight: bold; "
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #a7f3d0;"
                )
            elif p == TranslationProvider.OPENAI:
                model = self.settings.openai_model or "gpt-4o-mini"
                self.status_badge.setText(f"🌐 OpenAI ({model})")
                self.status_badge.setStyleSheet(
                    "background-color: #eff6ff; color: #1e40af; font-weight: bold; "
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #bfdbfe;"
                )
            elif p == TranslationProvider.GEMINI:
                model = self.settings.gemini_model or "gemini-1.5-flash"
                self.status_badge.setText(f"🌐 Gemini ({model})")
                self.status_badge.setStyleSheet(
                    "background-color: #eff6ff; color: #1e40af; font-weight: bold; "
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #bfdbfe;"
                )
            elif p == TranslationProvider.CLAUDE:
                model = self.settings.claude_model or "claude-3-5-haiku"
                self.status_badge.setText(f"🌐 Claude ({model})")
                self.status_badge.setStyleSheet(
                    "background-color: #faf5ff; color: #6b21a8; font-weight: bold; "
                    "padding: 4px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #e9d5ff;"
                )

    def _open_settings(self) -> None:
        dialog = ApiSettingsDialog(self)
        if dialog.exec():
            self.settings = SettingsManager.load_settings()
            for i in range(self.provider_combo.count()):
                if self.provider_combo.itemData(i) == self.settings.provider:
                    self.provider_combo.setCurrentIndex(i)
                    break
            self._update_status_badge()

    def set_result(self, result: Optional[AnonymizationResult]) -> None:
        self.current_result = result
        if not result:
            self.editor.setPlainText("")
            self._update_stats()
            return

        if result.english_report:
            self.editor.setPlainText(result.english_report)
        else:
            self.regenerate()

        self._update_stats()

    def regenerate(self) -> None:
        if not self.current_result:
            return

        provider = self.provider_combo.currentData()
        if isinstance(provider, TranslationProvider):
            self.settings.provider = provider

        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            report_text = generate_developer_report(self.current_result, self.settings)
            self.current_result.english_report = report_text
            self.editor.setPlainText(report_text)
            self._update_status_badge()
            self._update_stats()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Fehler bei der Generierung",
                f"Konnte englischen Report nicht erzeugen:\n{e}\n\n"
                "Tipp: Überprüfen Sie Ihren API-Schlüssel oder wählen Sie den lokalen Generator.",
            )
        finally:
            QGuiApplication.restoreOverrideCursor()

    def get_report_text(self) -> str:
        return self.editor.toPlainText()

    def _on_text_changed(self) -> None:
        text = self.editor.toPlainText()
        if self.current_result:
            self.current_result.english_report = text
        self._update_stats()
        self.report_edited.emit(text)

    def _update_stats(self) -> None:
        text = self.editor.toPlainText()
        chars = len(text)
        lines = len(text.splitlines()) if text else 0
        self.stats_label.setText(f"{chars} Zeichen | {lines} Zeilen")

    def _copy_to_clipboard(self) -> None:
        text = self.editor.toPlainText()
        if not text:
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            QMessageBox.information(
                self,
                "In Zwischenablage kopiert",
                "Der englische Entwickler-Report wurde in die Zwischenablage kopiert.",
            )

    def _save_single_report(self) -> None:
        text = self.editor.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "Kein Inhalt", "Es ist noch kein Report vorhanden.")
            return

        default_name = "summary_and_email_en.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Englischen Entwickler-Report speichern",
            default_name,
            "Textdateien (*.txt);;Markdown (*.md);;Alle Dateien (*.*)",
        )
        if file_path:
            try:
                Path(file_path).write_text(text, encoding="utf-8")
                QMessageBox.information(
                    self,
                    "Datei gespeichert",
                    f"Der englische Report wurde erfolgreich gespeichert:\n{file_path}",
                )
            except Exception as e:
                QMessageBox.critical(self, "Fehler beim Speichern", f"Konnte Datei nicht schreiben:\n{e}")
