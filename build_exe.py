"""Optimized PyInstaller build script to create a lightweight standalone executable for py-seudo."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
import PyInstaller.__main__


def build():
    root_dir = Path(__file__).resolve().parent
    src_dir = root_dir / "src"
    entry_point = src_dir / "py_seudo" / "main.py"
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"

    print("==================================================")
    print("Building py-seudo Optimized Standalone Executable")
    print(f"Entry point: {entry_point}")
    print(f"Dist dir:    {dist_dir}")
    print("==================================================")

    # Exclude unused Qt and stdlib modules to keep binary lean (~42 MB instead of ~250 MB)
    excluded_modules = [
        "PySide6.QtNetwork",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtQuick3D",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtSql",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtTest",
        "PySide6.QtXml",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPrintSupport",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtSensors",
        "PySide6.QtPositioning",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtSpatialAudio",
        "tkinter",
        "unittest",
    ]

    pyinstaller_args = [
        str(entry_point),
        "--name=py-seudo",
        "--noconsole",
        "--onefile",
        "--clean",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--paths={src_dir}",
        "--noconfirm",
    ]

    for mod in excluded_modules:
        pyinstaller_args.append(f"--exclude-module={mod}")

    PyInstaller.__main__.run(pyinstaller_args)

    exe_path = dist_dir / ("py-seudo.exe" if sys.platform == "win32" else "py-seudo")
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print("==================================================")
        print("SUCCESS: Optimized executable created at:")
        print(f"  {exe_path}")
        print(f"  Size: {size_mb:.1f} MB (reduced from ~247 MB)")
        print("==================================================")
    else:
        print("ERROR: Executable was not found after build!")
        sys.exit(1)


if __name__ == "__main__":
    build()
