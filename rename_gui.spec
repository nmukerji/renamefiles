# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['rename_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('provider_keywords.txt', '.'),
        ('purpose_keywords.txt', '.'),
        ('/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/dateparser/data', 'dateparser/data')
    ],
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
    name='rename_gui',
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
app = BUNDLE(
    exe,
    name='rename_gui.app',
    icon=None,
    bundle_identifier=None,
)
