# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path(SPECPATH).resolve().parent


hiddenimports = collect_submodules("cheburnet")

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "assets/cheburnet.ico"), "assets"),
        (str(ROOT / "assets/cheburnet.png"), "assets"),
        (str(ROOT / "cheburnet/app/assets/icons/chevron-down.svg"), "cheburnet/app/assets/icons"),
        (str(ROOT / "cheburnet/app/assets/icons/check.svg"), "cheburnet/app/assets/icons"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CheburNet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ROOT / "assets/cheburnet.ico")],
    version=str(ROOT / "build_scripts/version_info.txt"),
    uac_admin=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CheburNet",
)
