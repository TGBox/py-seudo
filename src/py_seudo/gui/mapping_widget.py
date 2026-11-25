"""Interactive mapping table and audit inspection widget with GDPR security safeguards."""
from __future__ import annotations

import html
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from py_seudo.engine import PseudoEngine
from py_seudo.models import AnonymizationResult, MappingEntry, ReplacementCategory, Suspicion


class AddMappingDialog(QDialog):
    """Dialog to manually add a custom replacement rule."""

    def __init__(self, parent: QWidget | None = None, original: str = ""):
        super().__init__(parent)
        self.setWindowTitle("➕ Neue Ersetzung manuell hinzufügen")
        self.setMinimumWidth(420)
        self._init_ui()
        if original:
            self.orig_edit.setText(original)
            self.pseudo_edit.setFocus()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info_lbl = QLabel(
            "Geben Sie den sensiblen Originalwert und das gewünschte Pseudonym an.\n"
            "Der Wert wird global in der Abrechnungsdatei und der E-Mail ersetzt."
        )
        info_lbl.setObjectName("MutedLabel")
        layout.addWidget(info_lbl)

        form = QFormLayout()
        self.orig_edit = QLineEdit()
        self.orig_edit.setPlaceholderText("z. B. Dr. Johannes Schmidt oder 108018132")

        self.pseudo_edit = QLineEdit()
        self.pseudo_edit.setPlaceholderText("z. B. Dr. med. Musterarzt_99 oder 999000009")

        self.cat_combo = QComboBox()
        self.cat_combo.setView(QListView())
        for cat in ReplacementCategory:
            self.cat_combo.addItem(cat.value, cat)

        form.addRow("Original (Sensibel):", self.orig_edit)
        form.addRow("Pseudonym (Ersatz):", self.pseudo_edit)
        form.addRow("Kategorie:", self.cat_combo)

        layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Hinzufügen & Ersetzen")
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_accept(self) -> None:
        orig = self.orig_edit.text().strip()
        pseudo = self.pseudo_edit.text().strip()
        if not orig:
            QMessageBox.warning(self, "Fehlende Eingabe", "Bitte geben Sie einen Originalwert ein.")
            return
        if not pseudo:
            QMessageBox.warning(self, "Fehlende Eingabe", "Bitte geben Sie ein Pseudonym ein.")
            return
        self.accept()

    def get_entry(self) -> MappingEntry:
        data = self.cat_combo.currentData()
        if isinstance(data, ReplacementCategory):
            cat = data
        elif isinstance(data, str):
            try:
                cat = ReplacementCategory(data)
            except ValueError:
                try:
                    cat = ReplacementCategory[data]
                except KeyError:
                    cat = ReplacementCategory.OTHER
        else:
            cat = ReplacementCategory.OTHER

        return MappingEntry(
            original=self.orig_edit.text().strip(),
            pseudonym=self.pseudo_edit.text().strip(),
            category=cat,
            count=1,
            description="Manuell hinzugefügte Ersetzung",
            is_manual=True,
        )


class SuspicionReviewDialog(QDialog):
    """Verdachtsfaelle einzeln pruefen: ersetzen oder ausdruecklich freigeben.

    Es gibt bewusst keinen Knopf "alle freigeben". Jede Stelle muss einzeln
    angehakt werden, damit die Freigabe eine Entscheidung ist und kein Reflex.
    """

    ACTION_ACKNOWLEDGE = "acknowledge"
    ACTION_REPLACE = "replace"

    def __init__(self, suspicions: List[Suspicion], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("🔎 Verdachtsfälle prüfen")
        self.setMinimumSize(640, 420)
        self.action: Optional[str] = None
        self.selected_texts: List[str] = []
        self._init_ui(suspicions)

    def _init_ui(self, suspicions: List[Suspicion]) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(
            "Diese Stellen sehen nach Personenbezug aus und stehen noch im Output.\n\n"
            "• Echte Personen- oder Praxisdaten: einzeln markieren und „Ersetzen…“ wählen.\n"
            "• Unkritisch (z. B. Kassen-IK, technische Nummer): anhaken und freigeben.\n\n"
            "Solange eine Stelle offen ist, bleiben Export und KI-Versand gesperrt."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.list_widget = QListWidget()
        for s in suspicions:
            item = QListWidgetItem(f"Zeile {s.line}:  {s.text}   —   {s.reason}")
            item.setData(Qt.ItemDataRole.UserRole, s.text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list_widget.addItem(item)
        self.list_widget.itemChanged.connect(self._update_buttons)
        layout.addWidget(self.list_widget, 1)

        buttons = QHBoxLayout()
        self.replace_btn = QPushButton("➕ Ersetzen…")
        self.replace_btn.setToolTip("Genau eine Stelle anhaken, um sie durch ein Pseudonym zu ersetzen")
        self.replace_btn.clicked.connect(self._on_replace)
        self.ack_btn = QPushButton("✓ Angehakte als unkritisch freigeben")
        self.ack_btn.clicked.connect(self._on_acknowledge)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.replace_btn)
        buttons.addStretch()
        buttons.addWidget(self.ack_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)
        self._update_buttons()

    def _checked_texts(self) -> List[str]:
        texts = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                texts.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return texts

    def _update_buttons(self, *_args) -> None:
        checked = self._checked_texts()
        self.replace_btn.setEnabled(len(checked) == 1)
        self.ack_btn.setEnabled(len(checked) > 0)

    def _on_replace(self) -> None:
        self.action = self.ACTION_REPLACE
        self.selected_texts = self._checked_texts()
        self.accept()

    def _on_acknowledge(self) -> None:
        texts = self._checked_texts()
        reply = QMessageBox.question(
            self,
            "Freigabe bestätigen",
            f"{len(texts)} Stelle(n) als unkritisch freigeben?\n\n"
            "Diese Werte werden danach unverändert exportiert und dürfen an "
            "externe Dienste übermittelt werden.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.action = self.ACTION_ACKNOWLEDGE
        self.selected_texts = texts
        self.accept()

    def get_decision(self) -> Tuple[Optional[str], List[str]]:
        return self.action, self.selected_texts


class MappingWidget(QWidget):
    """Table widget showing all detected entities, originals, and pseudonyms."""

    mapping_updated = Signal(str, str, str)  # (original, old_pseudo, new_pseudo)
    mapping_added = Signal(object)           # (MappingEntry)
    suspicions_acknowledged = Signal(list)   # (List[str]) ausdruecklich freigegebene Texte

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.current_result: AnonymizationResult | None = None
        self.all_mappings: List[MappingEntry] = []
        self._is_populating = False
        self.is_dark_mode = True
        self._init_ui()

    def update_theme(self, is_dark: bool) -> None:
        self.is_dark_mode = is_dark
        if self.all_mappings:
            self._populate_table(self.all_mappings)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Control Bar
        ctrl_bar = QHBoxLayout()

        self.summary_label = QLabel("Keine Mappings geladen")
        self.summary_label.setObjectName("SummaryLabel")

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 In Mappings filtern...")
        self.search_box.textChanged.connect(self._filter_mappings)
        self.search_box.setMaximumWidth(280)

        self.add_btn = QPushButton("➕ Neue Ersetzung...")
        self.add_btn.setToolTip("Übersehene sensible Stelle manuell zur Ersetzungstabelle hinzufügen")
        self.add_btn.clicked.connect(lambda: self._open_add_mapping_dialog())
        self.add_btn.setEnabled(False)

        self.export_btn = QPushButton("🛡️ Mapping-Tabelle exportieren (Audit)...")
        self.export_btn.clicked.connect(self._export_mapping_audit)
        self.export_btn.setEnabled(False)

        ctrl_bar.addWidget(self.summary_label)
        ctrl_bar.addStretch()
        ctrl_bar.addWidget(self.search_box)
        ctrl_bar.addWidget(self.add_btn)
        ctrl_bar.addWidget(self.export_btn)
        layout.addLayout(ctrl_bar)

        # Security Banner
        self.security_banner = QLabel(
            "🔒 DSGVO-Schutz: Diese Zuordnungen verbleiben standardmäßig ausschließlich im Arbeitsspeicher "
            "und werden niemals automatisch in Dateien oder Git gespeichert."
        )
        self.security_banner.setObjectName("SecurityBanner")
        layout.addWidget(self.security_banner)

        # Restrisiko: Stellen, die nach Personenbezug aussehen, aber nicht
        # ersetzt wurden. Standardmaessig ausgeblendet -- erscheint nur bei Funden.
        self.suspicion_banner = QLabel()
        self.suspicion_banner.setObjectName("SuspicionBanner")
        self.suspicion_banner.setWordWrap(True)
        self.suspicion_banner.hide()
        layout.addWidget(self.suspicion_banner)

        review_row = QHBoxLayout()
        self.review_btn = QPushButton("🔎 Verdachtsfälle prüfen…")
        self.review_btn.setToolTip("Offene Stellen einzeln ersetzen oder als unkritisch freigeben")
        self.review_btn.clicked.connect(lambda: self.open_suspicion_review())
        self.review_btn.hide()
        review_row.addWidget(self.review_btn)
        review_row.addStretch()
        layout.addLayout(review_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Kategorie",
            "Original (Sensibel)",
            "Pseudonym (Ersetzt)",
            "Anzahl",
            "Fehler-Spiegelung",
            "Details / Fundstelle",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(self._on_item_changed)

        layout.addWidget(self.table)

    def _open_add_mapping_dialog(self, original: str = "") -> None:
        dlg = AddMappingDialog(self, original=original)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            entry = dlg.get_entry()
            self.mapping_added.emit(entry)

    def open_suspicion_review(self) -> None:
        """Dialog zum Abarbeiten der offenen Verdachtsfaelle."""
        if not self.current_result or not self.current_result.suspicions:
            return
        dlg = SuspicionReviewDialog(list(self.current_result.suspicions), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        action, texts = dlg.get_decision()
        if action == SuspicionReviewDialog.ACTION_REPLACE and texts:
            self._open_add_mapping_dialog(original=texts[0])
        elif action == SuspicionReviewDialog.ACTION_ACKNOWLEDGE and texts:
            self.suspicions_acknowledged.emit(texts)

    def set_mappings(self, result: AnonymizationResult) -> None:
        self.current_result = result
        self.all_mappings = result.mappings
        self.export_btn.setEnabled(len(self.all_mappings) > 0)
        self.add_btn.setEnabled(True)

        self._update_summary_label()
        self._populate_table(self.all_mappings)
        self._show_suspicions(result)

    def _update_summary_label(self) -> None:
        if not self.current_result:
            return
        total_rep = sum(m.count for m in self.all_mappings)
        total_errors = sum(1 for m in self.all_mappings if m.error_mirrored)
        total_manual = sum(1 for m in self.all_mappings if m.is_manual)

        parts = [f"{len(self.all_mappings)} Entitäten ({total_rep} Ersetzungen)"]
        if total_errors > 0:
            parts.append(f"⚠️ {total_errors} gespiegelt")
        if total_manual > 0:
            parts.append(f"✏️ {total_manual} manuell")
        self.summary_label.setText(f"Ersetzungs-Protokoll: {', '.join(parts)}")

    def _show_suspicions(self, result: AnonymizationResult) -> None:
        """Restrisiko einblenden -- oder ausblenden, wenn nichts offen ist."""
        if not result.suspicions:
            self.suspicion_banner.hide()
            self.review_btn.hide()
            return

        # Inhalte stammen aus fremden Dateien -> fuer das Rich-Text-Label escapen.
        zeilen = "<br>".join(
            f"&nbsp;&nbsp;• Zeile {s.line}: <b>{html.escape(s.text)}</b> &mdash; {html.escape(s.reason)}"
            for s in result.suspicions[:12]
        )
        weitere = ""
        if len(result.suspicions) > 12:
            weitere = f"<br>&nbsp;&nbsp;… und {len(result.suspicions) - 12} weitere"

        self.suspicion_banner.setText(
            f"⚠️ <b>Restrisiko: {len(result.suspicions)} Stelle(n) konnten nicht sicher "
            f"zugeordnet werden.</b> Bitte pruefen Sie diese von Hand, bevor Sie die "
            f"Dateien weitergeben. Export und KI-Versand sind gesperrt, bis alle "
            f"Stellen ersetzt oder freigegeben sind:<br>{zeilen}{weitere}"
        )
        self.suspicion_banner.show()
        self.review_btn.show()

    def refresh_suspicions(self) -> None:
        """Nur die Restrisiko-Anzeige aktualisieren (nach recheck)."""
        if self.current_result is not None:
            self._show_suspicions(self.current_result)

    def _populate_table(self, mappings: List[MappingEntry]) -> None:
        self._is_populating = True
        try:
            self.table.setRowCount(len(mappings))
            for row, entry in enumerate(mappings):
                # Category
                cat_val = entry.category.value if isinstance(entry.category, ReplacementCategory) else str(entry.category)
                cat_item = QTableWidgetItem(cat_val)
                cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Original
                orig_item = QTableWidgetItem(entry.original)
                orig_item.setFlags(orig_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Pseudonym - Editable!
                pseudo_item = QTableWidgetItem(entry.pseudonym)
                pseudo_item.setFlags(pseudo_item.flags() | Qt.ItemFlag.ItemIsEditable)
                pseudo_item.setData(Qt.ItemDataRole.UserRole, entry.original)
                pseudo_item.setToolTip("Doppelklick zum manuellen Anpassen des Pseudowerts")

                # Count
                count_item = QTableWidgetItem(str(entry.count))
                count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Status badge (Error mirroring / manual)
                if self.is_dark_mode:
                    manual_color = QColor("#38bdf8")
                    mirrored_color = QColor("#fb923c")
                    valid_color = QColor("#34d399")
                else:
                    manual_color = QColor("#0369a1")
                    mirrored_color = QColor("#c2410c")
                    valid_color = QColor("#15803d")

                if entry.is_manual:
                    if entry.error_mirrored:
                        status_item = QTableWidgetItem("⚠️ Gespiegelt (✏️ Manuell)")
                        status_item.setToolTip(f"Manuell angepasst. {entry.diagnostic_note}")
                    else:
                        status_item = QTableWidgetItem("✏️ Manuell")
                        status_item.setToolTip("Dieser Pseudowert wurde manuell angepasst")
                    status_item.setForeground(manual_color)
                elif entry.error_mirrored:
                    status_item = QTableWidgetItem("⚠️ Gespiegelt")
                    status_item.setForeground(mirrored_color)
                    status_item.setToolTip(entry.diagnostic_note or "Fehlerhafter Wert wurde gespiegelt")
                else:
                    status_item = QTableWidgetItem("✓ Valide")
                    status_item.setForeground(valid_color)
                    status_item.setToolTip("Syntaktisch und mathematisch valider Pseudowert")
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Description
                desc_text = entry.description
                if entry.error_mirrored and entry.diagnostic_note and entry.diagnostic_note not in desc_text:
                    desc_text = f"{desc_text} ({entry.diagnostic_note})" if desc_text else entry.diagnostic_note
                desc_item = QTableWidgetItem(desc_text)
                desc_item.setToolTip(entry.diagnostic_note if entry.error_mirrored else "")
                desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.table.setItem(row, 0, cat_item)
                self.table.setItem(row, 1, orig_item)
                self.table.setItem(row, 2, pseudo_item)
                self.table.setItem(row, 3, count_item)
                self.table.setItem(row, 4, status_item)
                self.table.setItem(row, 5, desc_item)
        finally:
            self._is_populating = False

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._is_populating or item.column() != 2:
            return

        row = item.row()
        orig_key = item.data(Qt.ItemDataRole.UserRole)
        if not orig_key:
            return

        new_pseudo = item.text().strip()
        entry = next((m for m in self.all_mappings if m.original == orig_key), None)
        if not entry:
            return

        old_pseudo = entry.pseudonym
        if new_pseudo == old_pseudo:
            return

        entry.pseudonym = new_pseudo
        entry.is_manual = True

        self._is_populating = True
        try:
            status_item = self.table.item(row, 4)
            if status_item:
                if entry.error_mirrored:
                    status_item.setText("⚠️ Gespiegelt (✏️ Manuell)")
                    status_item.setToolTip(f"Manuell angepasst. {entry.diagnostic_note}")
                else:
                    status_item.setText("✏️ Manuell")
                    status_item.setToolTip("Dieser Pseudowert wurde manuell angepasst")
                status_item.setForeground(QColor("#38bdf8"))
        finally:
            self._is_populating = False

        self._update_summary_label()
        self.mapping_updated.emit(entry.original, old_pseudo, new_pseudo)

    def _filter_mappings(self, filter_text: str) -> None:
        q = filter_text.strip().lower()
        if not q:
            self._populate_table(self.all_mappings)
            return

        filtered = [
            m
            for m in self.all_mappings
            if q in m.original.lower()
            or q in m.pseudonym.lower()
            or q in (m.category.value if isinstance(m.category, ReplacementCategory) else str(m.category)).lower()
            or q in m.description.lower()
            or q in m.diagnostic_note.lower()
            or (q in "gespiegelt fehler" and m.error_mirrored)
            or (q in "valide" and not m.error_mirrored and not m.is_manual)
            or (q in "manuell angepasst" and m.is_manual)
        ]
        self._populate_table(filtered)

    def _export_mapping_audit(self) -> None:
        if not self.current_result or not self.all_mappings:
            return

        # Security confirmation dialog
        reply = QMessageBox.warning(
            self,
            "⚠️ DSGVO & Sicherheitswarnung",
            "ACHTUNG: Die exportierte Mapping-Datei enthält sensible Originaldaten "
            "(Patientennamen, KVNRs, Praxis-IKs) zusammen mit den Pseudonymen.\n\n"
            "Diese Datei darf NIEMALS an Dritte weitergegeben, in Online-Foren hochgeladen "
            "oder in ein Git-Repository committed werden!\n\n"
            "Möchten Sie die Datei dennoch zur internen Praxis-Dokumentation speichern?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Mapping-Tabelle speichern",
            "mapping_audit.json",
            "JSON-Datei (*.json);;CSV-Datei (*.csv)",
        )

        if file_path:
            p = Path(file_path)
            try:
                if p.suffix.lower() == ".csv":
                    PseudoEngine.export_audit_mapping_csv(self.current_result, p)
                else:
                    PseudoEngine.export_audit_mapping_json(self.current_result, p)

                QMessageBox.information(
                    self,
                    "Export erfolgreich",
                    f"Die Mapping-Audit-Datei wurde erfolgreich gespeichert unter:\n{file_path}\n\n"
                    "Hinweis: Die Datei ist durch die .gitignore dieses Projekts gegen versehentliches Committen geschützt.",
                )
            except Exception as e:
                QMessageBox.critical(self, "Fehler beim Export", f"Konnte Datei nicht speichern:\n{e}")
