"""Interactive mapping table and audit inspection widget with GDPR security safeguards."""
from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from py_seudo.engine import PseudoEngine
from py_seudo.models import AnonymizationResult, MappingEntry


class MappingWidget(QWidget):
    """Table widget showing all detected entities, originals, and pseudonyms."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.current_result: AnonymizationResult | None = None
        self.all_mappings: List[MappingEntry] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Control Bar
        ctrl_bar = QHBoxLayout()

        self.summary_label = QLabel("Keine Mappings geladen")
        self.summary_label.setStyleSheet("font-weight: 600; color: #38bdf8;")

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 In Mappings filtern...")
        self.search_box.textChanged.connect(self._filter_mappings)
        self.search_box.setMaximumWidth(280)

        self.export_btn = QPushButton("🛡️ Mapping-Tabelle exportieren (Audit)...")
        self.export_btn.clicked.connect(self._export_mapping_audit)
        self.export_btn.setEnabled(False)

        ctrl_bar.addWidget(self.summary_label)
        ctrl_bar.addStretch()
        ctrl_bar.addWidget(self.search_box)
        ctrl_bar.addWidget(self.export_btn)
        layout.addLayout(ctrl_bar)

        # Security Banner
        self.security_banner = QLabel(
            "🔒 DSGVO-Schutz: Diese Zuordnungen verbleiben standardmäßig ausschließlich im Arbeitsspeicher "
            "und werden niemals automatisch in Dateien oder Git gespeichert."
        )
        self.security_banner.setStyleSheet(
            "background-color: #1e3a8a; color: #93c5fd; padding: 6px 12px; "
            "border-radius: 6px; font-size: 11px;"
        )
        layout.addWidget(self.security_banner)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Kategorie",
            "Original (Sensibel)",
            "Pseudonym (Ersetzt)",
            "Anzahl",
            "Details / Fundstelle",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def set_mappings(self, result: AnonymizationResult) -> None:
        self.current_result = result
        self.all_mappings = result.mappings
        self.export_btn.setEnabled(len(self.all_mappings) > 0)

        total_rep = result.total_replacements
        self.summary_label.setText(
            f"Ersetzungs-Protokoll: {len(self.all_mappings)} eindeutige Entitäten ({total_rep} Ersetzungen insgesamt)"
        )
        self._populate_table(self.all_mappings)

    def _populate_table(self, mappings: List[MappingEntry]) -> None:
        self.table.setRowCount(len(mappings))
        for row, entry in enumerate(mappings):
            # Category
            cat_item = QTableWidgetItem(entry.category.value)
            cat_item.setFlags(cat_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            # Original
            orig_item = QTableWidgetItem(entry.original)
            orig_item.setFlags(orig_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            # Pseudonym
            pseudo_item = QTableWidgetItem(entry.pseudonym)
            pseudo_item.setFlags(pseudo_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            # Count
            count_item = QTableWidgetItem(str(entry.count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            count_item.setFlags(count_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            # Description
            desc_item = QTableWidgetItem(entry.description)
            desc_item.setFlags(desc_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(row, 0, cat_item)
            self.table.setItem(row, 1, orig_item)
            self.table.setItem(row, 2, pseudo_item)
            self.table.setItem(row, 3, count_item)
            self.table.setItem(row, 4, desc_item)

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
            or q in m.category.value.lower()
            or q in m.description.lower()
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
