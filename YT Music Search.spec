# -*- mode: python ; coding: utf-8 -*-

import os
import shutil

from PyInstaller.utils.hooks import collect_data_files

# Für die exe wird nie die eigene settings.json (persönlicher Pfad + echte API-Keys)
# gebündelt, sondern immer frisch aus settings.public.json gestaged - so bleibt die
# lokale Dev-settings.json unangetastet und jeder Build ist automatisch weitergabefähig.
_bin_dir = 'universaldownloader/bin'
_staging_dir = 'build/_public_settings'
os.makedirs(_staging_dir, exist_ok=True)
shutil.copy(os.path.join(_bin_dir, 'settings.public.json'), os.path.join(_staging_dir, 'settings.json'))

_bin_datas = [
    (os.path.join(_bin_dir, f), 'bin')
    for f in os.listdir(_bin_dir)
    if os.path.isfile(os.path.join(_bin_dir, f)) and f not in ('settings.json', 'settings.public.json')
]
_bin_datas.append((os.path.join(_staging_dir, 'settings.json'), 'bin'))

a = Analysis(
    ['universaldownloader\\main.py'],
    pathex=['universaldownloader'],
    binaries=[],
    datas=_bin_datas + [('universaldownloader/ffmpeg.exe', '.')]
        + collect_data_files('ttkbootstrap'),
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
    name='YT Music Search',
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
    icon=['universaldownloader/bin/icon.ico'],
)
