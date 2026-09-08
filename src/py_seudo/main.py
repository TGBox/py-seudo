"""Main entrypoint for py-seudo Desktop Application."""
from __future__ import annotations

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from py_seudo.gui.app import MainWindow


def main() -> int:
    """Launch the py-seudo Desktop Application."""
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setApplicationName("py-seudo")
        app.setOrganizationName("py-seudo")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
