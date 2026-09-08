"""API Settings Dialog for configuring OpenAI, Gemini, and Claude endpoints."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from py_seudo.translation.api_client import check_api_connection
from py_seudo.translation.models import TranslationProvider, TranslationSettings
from py_seudo.translation.settings_manager import SettingsManager


class ApiSettingsDialog(QDialog):
    """Configuration dialog for external translation & LLM providers."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ API-Einstellungen für KI-Übersetzung")
        self.resize(560, 420)
        self.settings = SettingsManager.load_settings()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info_label = QLabel(
            "Hinweis: Standardmäßig arbeitet py-seudo 100 % lokal und offline ohne API-Keys.\n"
            "Wenn Sie hier einen externen Dienst konfigurieren, wird dieser nur verwendet, wenn\n"
            "Sie ihn im Reiter 'Englisch' explizit als Anbieter auswählen."
        )
        info_label.setObjectName("MutedLabel")
        layout.addWidget(info_label)

        self.tab_widget = QTabWidget()

        # Tab 1: OpenAI
        openai_tab = QWidget()
        openai_layout = QFormLayout(openai_tab)
        openai_layout.setSpacing(10)

        self.openai_key_edit = QLineEdit(self.settings.openai_api_key)
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_edit.setPlaceholderText("sk-...")

        show_openai_btn = QPushButton("👁")
        show_openai_btn.setObjectName("IconButton")
        show_openai_btn.setFixedSize(32, 30)
        show_openai_btn.setCheckable(True)
        show_openai_btn.setToolTip("API-Schlüssel anzeigen")

        def _toggle_openai(checked: bool) -> None:
            self.openai_key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
            show_openai_btn.setText("🔒" if checked else "👁")
            show_openai_btn.setToolTip("API-Schlüssel verbergen" if checked else "API-Schlüssel anzeigen")

        show_openai_btn.toggled.connect(_toggle_openai)
        openai_key_row = QHBoxLayout()
        openai_key_row.addWidget(self.openai_key_edit)
        openai_key_row.addWidget(show_openai_btn)

        self.openai_model_edit = QLineEdit(self.settings.openai_model)
        self.openai_model_edit.setPlaceholderText("gpt-4o-mini")

        self.openai_base_url_edit = QLineEdit(self.settings.openai_base_url)
        self.openai_base_url_edit.setPlaceholderText("Standard: https://api.openai.com/v1 (oder z. B. http://localhost:11434/v1)")

        openai_layout.addRow("API-Schlüssel:", openai_key_row)
        openai_layout.addRow("Modell:", self.openai_model_edit)
        openai_layout.addRow("Basis-URL (optional):", self.openai_base_url_edit)

        test_openai_btn = QPushButton("🔌 OpenAI-Verbindung testen")
        test_openai_btn.clicked.connect(self._test_openai)
        openai_layout.addRow("", test_openai_btn)
        self.tab_widget.addTab(openai_tab, "OpenAI / Kompatibel")

        # Tab 2: Gemini
        gemini_tab = QWidget()
        gemini_layout = QFormLayout(gemini_tab)
        gemini_layout.setSpacing(10)

        self.gemini_key_edit = QLineEdit(self.settings.gemini_api_key)
        self.gemini_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_edit.setPlaceholderText("AIza...")

        show_gemini_btn = QPushButton("👁")
        show_gemini_btn.setObjectName("IconButton")
        show_gemini_btn.setFixedSize(32, 30)
        show_gemini_btn.setCheckable(True)
        show_gemini_btn.setToolTip("API-Schlüssel anzeigen")

        def _toggle_gemini(checked: bool) -> None:
            self.gemini_key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
            show_gemini_btn.setText("🔒" if checked else "👁")
            show_gemini_btn.setToolTip("API-Schlüssel verbergen" if checked else "API-Schlüssel anzeigen")

        show_gemini_btn.toggled.connect(_toggle_gemini)
        gemini_key_row = QHBoxLayout()
        gemini_key_row.addWidget(self.gemini_key_edit)
        gemini_key_row.addWidget(show_gemini_btn)

        self.gemini_model_edit = QLineEdit(self.settings.gemini_model)
        self.gemini_model_edit.setPlaceholderText("gemini-1.5-flash")

        gemini_layout.addRow("API-Schlüssel:", gemini_key_row)
        gemini_layout.addRow("Modell:", self.gemini_model_edit)

        test_gemini_btn = QPushButton("🔌 Gemini-Verbindung testen")
        test_gemini_btn.clicked.connect(self._test_gemini)
        gemini_layout.addRow("", test_gemini_btn)
        self.tab_widget.addTab(gemini_tab, "Google Gemini")

        # Tab 3: Claude
        claude_tab = QWidget()
        claude_layout = QFormLayout(claude_tab)
        claude_layout.setSpacing(10)

        self.claude_key_edit = QLineEdit(self.settings.claude_api_key)
        self.claude_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.claude_key_edit.setPlaceholderText("sk-ant-...")

        show_claude_btn = QPushButton("👁")
        show_claude_btn.setObjectName("IconButton")
        show_claude_btn.setFixedSize(32, 30)
        show_claude_btn.setCheckable(True)
        show_claude_btn.setToolTip("API-Schlüssel anzeigen")

        def _toggle_claude(checked: bool) -> None:
            self.claude_key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
            show_claude_btn.setText("🔒" if checked else "👁")
            show_claude_btn.setToolTip("API-Schlüssel verbergen" if checked else "API-Schlüssel anzeigen")

        show_claude_btn.toggled.connect(_toggle_claude)
        claude_key_row = QHBoxLayout()
        claude_key_row.addWidget(self.claude_key_edit)
        claude_key_row.addWidget(show_claude_btn)

        self.claude_model_edit = QLineEdit(self.settings.claude_model)
        self.claude_model_edit.setPlaceholderText("claude-3-5-haiku-20241022")

        claude_layout.addRow("API-Schlüssel:", claude_key_row)
        claude_layout.addRow("Modell:", self.claude_model_edit)

        test_claude_btn = QPushButton("🔌 Claude-Verbindung testen")
        test_claude_btn.clicked.connect(self._test_claude)
        claude_layout.addRow("", test_claude_btn)
        self.tab_widget.addTab(claude_tab, "Anthropic Claude")

        layout.addWidget(self.tab_widget)

        # Dialog Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._save)

        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)

        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def _get_current_draft_settings(self) -> TranslationSettings:
        return TranslationSettings(
            provider=self.settings.provider,
            openai_api_key=self.openai_key_edit.text().strip(),
            openai_model=self.openai_model_edit.text().strip() or "gpt-4o-mini",
            openai_base_url=self.openai_base_url_edit.text().strip(),
            gemini_api_key=self.gemini_key_edit.text().strip(),
            gemini_model=self.gemini_model_edit.text().strip() or "gemini-1.5-flash",
            claude_api_key=self.claude_key_edit.text().strip(),
            claude_model=self.claude_model_edit.text().strip() or "claude-3-5-haiku-20241022",
        )

    def _test_openai(self) -> None:
        draft = self._get_current_draft_settings()
        ok, msg = check_api_connection(TranslationProvider.OPENAI, draft)
        if ok:
            QMessageBox.information(self, "Verbindungstest erfolgreich", f"OpenAI API erreichbar:\n{msg}")
        else:
            QMessageBox.critical(self, "Verbindungsfehler", f"OpenAI-Aufruf fehlgeschlagen:\n{msg}")

    def _test_gemini(self) -> None:
        draft = self._get_current_draft_settings()
        ok, msg = check_api_connection(TranslationProvider.GEMINI, draft)
        if ok:
            QMessageBox.information(self, "Verbindungstest erfolgreich", f"Google Gemini API erreichbar:\n{msg}")
        else:
            QMessageBox.critical(self, "Verbindungsfehler", f"Gemini-Aufruf fehlgeschlagen:\n{msg}")

    def _test_claude(self) -> None:
        draft = self._get_current_draft_settings()
        ok, msg = check_api_connection(TranslationProvider.CLAUDE, draft)
        if ok:
            QMessageBox.information(self, "Verbindungstest erfolgreich", f"Anthropic Claude API erreichbar:\n{msg}")
        else:
            QMessageBox.critical(self, "Verbindungsfehler", f"Claude-Aufruf fehlgeschlagen:\n{msg}")

    def _save(self) -> None:
        updated = self._get_current_draft_settings()
        SettingsManager.save_settings(updated)
        self.settings = updated
        self.accept()
