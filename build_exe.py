"""PyInstaller build script to create a standalone executable for py-seudo."""
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
    print("Building py-seudo Standalone Executable with PyInstaller")
    print(f"Entry point: {entry_point}")
    print(f"Dist dir:    {dist_dir}")
    print("==================================================")

    pyinstaller_args = [
        str(entry_point),
        "--name=py-seudo",
        "--noconsole",
        "--onefile",
        "--clean",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--paths={src_dir}",
        # Collect PySide6 dependencies
        "--collect-all=PySide6",
        "--noconfirm",
    ]

    PyInstaller.__main__.run(pyinstaller_args)

    exe_path = dist_dir / ("py-seudo.exe" if sys.platform == "win32" else "py-seudo")
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print("==================================================")
        print(f"SUCCESS: Executable created at:")
        print(f"  {exe_path}")
        print(f"  Size: {size_mb:.1f} MB")
        print("==================================================")
    else:
        print("ERROR: Executable was not found after build!")
        sys.exit(1)


if __name__ == "__main__":
    build()
