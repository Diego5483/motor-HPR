# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['HPR/src/desktop/app.py'],
    pathex=[],
    binaries=[],
    datas=[('HPR/src/data/ceo_knowledge_base.json', '.'), ('HPR/src/desktop/assets/hpr.ico', 'HPR/src/desktop/assets'), ('HPR/src/desktop/assets/hpr_logo.png', 'HPR/src/desktop/assets'), ('HPR/src/core/engine.py', 'HPR/src/core'), ('HPR/src/core/triage.py', 'HPR/src/core'), ('HPR/src/core/security_agent.py', 'HPR/src/core'), ('HPR/src/desktop/agent.py', 'HPR/src/desktop'), ('HPR/src/desktop/voice.py', 'HPR/src/desktop'), ('HPR/src/models/contracts.py', 'HPR/src/models')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    exclude_binaries=True,
    name='Motor HPR',
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
    icon=['HPR/src/desktop/assets/hpr.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Motor HPR',
)
