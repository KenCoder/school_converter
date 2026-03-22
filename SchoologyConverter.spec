# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

_spec_dir = os.path.dirname(os.path.abspath(SPEC))
_codesign_identity = os.environ.get("APPLE_CODESIGN_IDENTITY") or None
_entitlements_file = (
    os.path.join(_spec_dir, "packaging/macos/entitlements.plist")
    if _codesign_identity
    else None
)
# UPX-packed binaries break codesign / notarization; disable when using Developer ID.
_use_upx = not bool(_codesign_identity)

a = Analysis(
    ['run_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('cc_converter/template.docx', 'cc_converter'),
        ('cc_converter/templates', 'cc_converter/templates'),
        ('cc_converter/file_handler.html', 'cc_converter'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',
        'webview.platforms.cocoa',
        'cc_converter.gui',
        'cc_converter.hierarchy_converter',
        'cc_converter.docx_converter',
        'cc_converter.xml_parser',
        'cc_converter.models',
        'docx',
        'docx.opc',
        'docx.oxml',
        'docx.shared',
        'docx.enum',
        'watchdog',
        'watchdog.observers',
        'watchdog.events',
        'requests',
        'pathlib',
        'json',
        'threading',
        'logging',
        'datetime',
        'zipfile',
        'html',
        'subprocess',
        'platform',
        'sys',
        'os',
    ],
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
    a.zipfiles,
    a.datas,
    [],
    name='SchoologyConverter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=_use_upx,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=_codesign_identity,
    entitlements_file=_entitlements_file,
)

# For macOS, create a proper .app bundle
app = BUNDLE(
    exe,
    name='SchoologyConverter.app',
    icon=None,
    bundle_identifier='io.github.kencoder.schoologyconverter',
    info_plist={
        'CFBundleName': 'Schoology Converter',
        'CFBundleDisplayName': 'Schoology Converter',
        'CFBundleIdentifier': 'io.github.kencoder.schoologyconverter',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': '????',
        'LSMinimumSystemVersion': '10.13.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
    },
) 