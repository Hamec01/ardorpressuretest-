# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/wika_report/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('config.json', '.'),
        ('resources/app_icon.ico', 'resources'),
        ('resources/logo.png', 'resources'),
    ],
    hiddenimports=[
        'openpyxl',
        'matplotlib',
        'pandas',
        'charset_normalizer',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.ttk',
        'fpdf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest'],
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
    name='WIKA CPG1500 Processor',
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
    icon='resources/app_icon.ico',
)
