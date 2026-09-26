# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for WallForge macOS App Bundle."""

import os
from pathlib import Path

block_cipher = None

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

datas = [
    (os.path.join(root_dir, 'packaging', 'icons', 'org.wallforge.app.svg'), 'icons'),
    (os.path.join(root_dir, 'packaging', 'icons', 'wallforge_512x512.png'), 'icons'),
]

hiddenimports = [
    'gi',
    'gi.repository.GLib',
    'gi.repository.GObject',
    'gi.repository.Gio',
    'gi.repository.Gtk',
    'gi.repository.Gdk',
    'gi.repository.Adw',
    'gi.repository.GdkPixbuf',
    'PIL',
    'PIL.Image',
    'requests',
    'json',
    'sqlite3',
    'hashlib',
    'concurrent.futures',
]

a = Analysis(
    [os.path.join(root_dir, 'run.py')],
    pathex=[root_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WallForge',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WallForge',
)

app = BUNDLE(
    coll,
    name='WallForge.app',
    icon=os.path.join(root_dir, 'packaging', 'icons', 'wallforge.icns') if os.path.exists(os.path.join(root_dir, 'packaging', 'icons', 'wallforge.icns')) else None,
    bundle_identifier='org.wallforge.app',
    info_plist=os.path.join(root_dir, 'packaging', 'macos', 'Info.plist'),
)
