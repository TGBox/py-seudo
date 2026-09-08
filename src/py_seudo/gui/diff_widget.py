"""Side-by-side synchronized comparison widget with diff highlighting."""
from __future__ import annotations

import difflib
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SynchronizedPlainTextEdit(QPlainTextEdit):
    """Text edit that syncs vertical scrollbar with a partner text edit."""

    def __init__(self, partner: QPlainTextEdit | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.partner = partner
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.verticalScrollBar().valueChanged.connect(self._sync_scroll)

    def set_partner(self, partner: QPlainTextEdit) -> None:
        self.partner = partner

    def _sync_scroll(self, value: int) -> None:
        if self.partner and self.partner.verticalScrollBar().value() != value:
            self.partner.verticalScrollBar().setValue(value)


class DiffWidget(QWidget):
    """Side-by-side comparison widget for Original vs. Anonymized content."""

    def __init__(self, title: str = "Vergleich", parent: QWidget | None = None):
        super().__init__(parent)
        self.title = title
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        self.title_label = QLabel(f"<b>{self.title}</b>")
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #38bdf8; font-weight: 500;")

        self.copy_btn = QPushButton("📋 Anonymisierten Text kopieren")
        self.copy_btn.clicked.connect(self._copy_anonymized)

        toolbar.addWidget(self.title_label)
        toolbar.addWidget(self.stats_label)
        toolbar.addStretch()
        toolbar.addWidget(self.copy_btn)
        main_layout.addLayout(toolbar)

        # Comparison Layout
        split_layout = QHBoxLayout()
        split_layout.setSpacing(8)

        # Left: Original
        left_col = QVBoxLayout()
        self.left_label = QLabel("Original (Sensible Echtdaten)")
        self.left_label.setStyleSheet("color: #ef4444; font-weight: 600;")
        self.left_edit = SynchronizedPlainTextEdit()
        self.left_edit.setReadOnly(True)
        left_col.addWidget(self.left_label)
        left_col.addWidget(self.left_edit)

        # Right: Anonymized
        right_col = QVBoxLayout()
        self.right_label = QLabel("Anonymisiert (DSGVO-konform)")
        self.right_label.setStyleSheet("color: #10b981; font-weight: 600;")
        self.right_edit = SynchronizedPlainTextEdit()
        self.right_edit.setReadOnly(True)
        right_col.addWidget(self.right_label)
        right_col.addWidget(self.right_edit)

        # Connect mutual scroll synchronization
        self.left_edit.set_partner(self.right_edit)
        self.right_edit.set_partner(self.left_edit)

        split_layout.addLayout(left_col, 1)
        split_layout.addLayout(right_col, 1)
        main_layout.addLayout(split_layout)

    def set_content(self, original_text: str, anonymized_text: str) -> None:
        """Populate panes and highlight modified lines."""
        self.left_edit.setPlainText(original_text)
        self.right_edit.setPlainText(anonymized_text)

        orig_lines = original_text.splitlines()
        anon_lines = anonymized_text.splitlines()

        # Compute diff count
        diff_count = 0
        max_lines = max(len(orig_lines), len(anon_lines))
        for i in range(max_lines):
            l_orig = orig_lines[i] if i < len(orig_lines) else ""
            l_anon = anon_lines[i] if i < len(anon_lines) else ""
            if l_orig != l_anon:
                diff_count += 1

        self.stats_label.setText(f"({diff_count} geänderte Zeilen / Segmente)")

        # Highlight changed lines in the right edit
        self._highlight_diffs(orig_lines, anon_lines)

    def _highlight_diffs(self, orig_lines: list[str], anon_lines: list[str]) -> None:
        """Apply green background highlight to lines that were modified."""
        cursor = QTextCursor(self.right_edit.document())
        cursor.beginEditBlock()

        fmt_changed = QTextCharFormat()
        fmt_changed.setBackground(QColor(16, 185, 129, 45))  # Subtle green

        max_lines = max(len(orig_lines), len(anon_lines))
        for i in range(len(anon_lines)):
            l_orig = orig_lines[i] if i < len(orig_lines) else None
            l_anon = anon_lines[i]
            if l_orig != l_anon:
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                for _ in range(i):
                    cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.mergeCharFormat(fmt_changed)

        cursor.endEditBlock()

    def _copy_anonymized(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.right_edit.toPlainText())
            self.stats_label.setText("✓ In Zwischenablage kopiert!")
