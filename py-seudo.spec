# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/droesch/Documents/Programmiertes/py-seudo/src/py_seudo/main.py'],
    pathex=['C:/Users/droesch/Documents/Programmiertes/py-seudo/src'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQuick3D', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtSql', 'PySide6.QtSvg', 'PySide6.QtSvgWidgets', 'PySide6.QtTest', 'PySide6.QtXml', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'PySide6.QtPrintSupport', 'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtSensors', 'PySide6.QtPositioning', 'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtSpatialAudio', 'tkinter', 'unittest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='py-seudo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
