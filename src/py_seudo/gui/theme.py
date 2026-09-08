"""Modern Light and Dark theme stylesheets for PySide6."""

DARK_THEME = """
QMainWindow, QDialog {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #f8fafc;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

QGroupBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #38bdf8;
}

QTabWidget::pane {
    border: 1px solid #334155;
    border-radius: 8px;
    background-color: #1e293b;
    top: -1px;
}

QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    border: 1px solid #334155;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 4px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #1e293b;
    color: #38bdf8;
    border-bottom: 2px solid #38bdf8;
    font-weight: 600;
}

QTabBar::tab:hover:!selected {
    background-color: #1a2538;
    color: #cbd5e1;
}

QPushButton {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 7px 15px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #475569;
    border-color: #64748b;
}

QPushButton:pressed {
    background-color: #1e293b;
}

QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}

QPushButton#PrimaryButton {
    background-color: #4f46e5;
    color: #ffffff;
    border: 1px solid #6366f1;
    font-size: 14px;
    font-weight: 600;
    padding: 9px 20px;
}

QPushButton#PrimaryButton:hover {
    background-color: #4338ca;
    border-color: #818cf8;
}

QPushButton#PrimaryButton:pressed {
    background-color: #3730a3;
}

QPushButton#SuccessButton {
    background-color: #059669;
    color: #ffffff;
    border: 1px solid #10b981;
}

QPushButton#SuccessButton:hover {
    background-color: #047857;
}

QPushButton#IconButton, QPushButton#ClearButton {
    padding: 0px;
    margin: 0px;
    min-width: 32px;
    max-width: 32px;
    min-height: 30px;
    max-height: 30px;
    font-family: 'Segoe UI Emoji', 'Segoe UI Symbol', 'Segoe UI', sans-serif;
    font-size: 14px;
    font-weight: bold;
    text-align: center;
}

QPushButton#ClearButton:hover {
    background-color: #7f1d1d;
    color: #fca5a5;
    border-color: #ef4444;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #4f46e5;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #38bdf8;
}

QComboBox {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 20px;
}

QComboBox:hover {
    border-color: #475569;
}

QComboBox:focus, QComboBox:on {
    border-color: #38bdf8;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #334155;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    background-color: #1e293b;
}

QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #94a3b8;
}

QComboBox::down-arrow:hover {
    border-top: 5px solid #f8fafc;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #4f46e5;
    selection-color: #ffffff;
    outline: 0px;
}

QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 6px 10px;
    border-radius: 4px;
    color: #f8fafc;
    background-color: #1e293b;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #334155;
    color: #f8fafc;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #4f46e5;
    color: #ffffff;
}

QMenu {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 4px;
    color: #f8fafc;
}

QMenu::item:selected {
    background-color: #4f46e5;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #334155;
    margin: 4px 8px;
}

QTableWidget {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    gridline-color: #1e293b;
    selection-background-color: #312e81;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #334155;
    font-weight: 600;
}

QScrollBar:vertical {
    background-color: #0f172a;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #334155;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #0f172a;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #334155;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #475569;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QStatusBar {
    background-color: #0f172a;
    border-top: 1px solid #1e293b;
    color: #94a3b8;
}
"""

LIGHT_THEME = """
QMainWindow, QDialog {
    background-color: #f8fafc;
    color: #0f172a;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #0f172a;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #0284c7;
}

QTabWidget::pane {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background-color: #ffffff;
    top: -1px;
}

QTabBar::tab {
    background-color: #f1f5f9;
    color: #64748b;
    border: 1px solid #e2e8f0;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 4px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0284c7;
    border-bottom: 2px solid #0284c7;
    font-weight: 600;
}

QTabBar::tab:hover:!selected {
    background-color: #e2e8f0;
    color: #334155;
}

QPushButton {
    background-color: #f1f5f9;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 15px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #e2e8f0;
    border-color: #94a3b8;
}

QPushButton:pressed {
    background-color: #cbd5e1;
}

QPushButton:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QPushButton#PrimaryButton {
    background-color: #4f46e5;
    color: #ffffff;
    border: 1px solid #4338ca;
    font-size: 14px;
    font-weight: 600;
    padding: 9px 20px;
}

QPushButton#PrimaryButton:hover {
    background-color: #4338ca;
}

QPushButton#PrimaryButton:pressed {
    background-color: #3730a3;
}

QPushButton#SuccessButton {
    background-color: #10b981;
    color: #ffffff;
    border: 1px solid #059669;
}

QPushButton#SuccessButton:hover {
    background-color: #059669;
}

QPushButton#IconButton, QPushButton#ClearButton {
    padding: 0px;
    margin: 0px;
    min-width: 32px;
    max-width: 32px;
    min-height: 30px;
    max-height: 30px;
    font-family: 'Segoe UI Emoji', 'Segoe UI Symbol', 'Segoe UI', sans-serif;
    font-size: 14px;
    font-weight: bold;
    text-align: center;
}

QPushButton#ClearButton:hover {
    background-color: #fee2e2;
    color: #dc2626;
    border-color: #ef4444;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #c7d2fe;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #0284c7;
}

QComboBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 20px;
}

QComboBox:hover {
    border-color: #94a3b8;
}

QComboBox:focus, QComboBox:on {
    border-color: #0284c7;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #cbd5e1;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    background-color: #f1f5f9;
}

QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #64748b;
}

QComboBox::down-arrow:hover {
    border-top: 5px solid #0f172a;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #e0e7ff;
    selection-color: #1e1b4b;
    outline: 0px;
}

QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 6px 10px;
    border-radius: 4px;
    color: #0f172a;
    background-color: #ffffff;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #f1f5f9;
    color: #0f172a;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #e0e7ff;
    color: #1e1b4b;
}

QMenu {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 4px;
    color: #0f172a;
}

QMenu::item:selected {
    background-color: #e0e7ff;
    color: #1e1b4b;
}

QMenu::separator {
    height: 1px;
    background-color: #e2e8f0;
    margin: 4px 8px;
}

QTableWidget {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    gridline-color: #f1f5f9;
    selection-background-color: #e0e7ff;
    selection-color: #1e1b4b;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #64748b;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
    font-weight: 600;
}

QScrollBar:vertical {
    background-color: #f8fafc;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #f8fafc;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QStatusBar {
    background-color: #f8fafc;
    border-top: 1px solid #e2e8f0;
    color: #64748b;
}
"""
