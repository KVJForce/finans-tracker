# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build configuration for the Finance Tracker executable.

Build with:
    pyinstaller FinanceTracker.spec
"""

from PyInstaller.utils.hooks import collect_data_files

# CustomTkinter ships theme JSON files and assets that must travel with the exe.
datas = collect_data_files("customtkinter")
# Window/exe icon, read at runtime through sys._MEIPASS.
datas += [("assets/finans_tracker.ico", "assets")]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="FinanceTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/finans_tracker.ico",
)
