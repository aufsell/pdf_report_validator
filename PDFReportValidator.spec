# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — собирает app/main.py + src/ в один исполняемый файл

import os, sys

block_cipher = None

a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=[],
    # Включаем весь src/ как данные — pyinstaller не видит динамические импорты
    datas=[
        ('src', 'src'),
    ],
    hiddenimports=[
        'src.models.message',
        'src.models.structured_document',
        'src.type_parser.parser',
        'src.type_parser.utils',
        'src.parsers_matcher.matcher',
        'src.parsers.base_parser',
        'src._pdf_parser.parser',
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
    name='PDFReportValidator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # windowed (без терминала)
    icon=None,              # можно добавить .ico/.icns
)
