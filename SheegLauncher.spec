# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH)

datas = [
    (str(project_root / "config" / "default.json"), "config"),
    (str(project_root / "scripts" / "GameScript" / "researchGamesLSL.exe"), "scripts/GameScript"),
    (str(project_root / "scripts" / "GameScript" / "researchGamesLSL.pck"), "scripts/GameScript"),
]

a = Analysis(
    [str(project_root / "sheeg_launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=["pylsl"],
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
    name="SheegLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
