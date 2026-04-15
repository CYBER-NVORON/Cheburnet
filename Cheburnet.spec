# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules


block_cipher = None

hiddenimports = collect_submodules("cheburnet")

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("assets/cheburnet.ico", "assets"),
        ("assets/cheburnet.png", "assets"),
        ("data/ru_whitelist_sample.txt", "data"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Cheburnet",
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
    icon=["assets/cheburnet.ico"],
    version="build_scripts/version_info.txt",
    uac_admin=True,
)
