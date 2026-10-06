# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import glob
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

BASE_DIR = os.path.abspath(SPECPATH)

# 1. Gom các file dữ liệu cần thiết (Model PaddleX, Icon)
datas = [
    (os.path.join(BASE_DIR, 'requirements.txt'), '.'),
    (os.path.join(BASE_DIR, 'app_icon.ico'), '.'),
]

models_dir = os.path.join(BASE_DIR, 'models')
if os.path.exists(models_dir):
    datas.append((models_dir, 'models'))

# 2. Gom các DLL của PyTorch và Paddle để khắc phục triệt để WinError 127
binaries = []
torch_lib_dir = r'D:\python\Lib\site-packages\torch\lib'
if os.path.exists(torch_lib_dir):
    for dll_file in glob.glob(os.path.join(torch_lib_dir, '*.dll')):
        binaries.append((dll_file, '.'))
        binaries.append((dll_file, 'torch/lib'))

paddle_libs_dir = r'D:\python\Lib\site-packages\paddle\libs'
if os.path.exists(paddle_libs_dir):
    for dll_file in glob.glob(os.path.join(paddle_libs_dir, '*.dll')):
        binaries.append((dll_file, '.'))
        binaries.append((dll_file, 'paddle/libs'))

# 3. Thu thập toàn bộ submodules của PaddleX và PaddleOCR
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtSvg',
    'cv2',
    'numpy',
    'pandas',
    'openpyxl',
    'rapidfuzz',
    'paddle',
    'paddleocr',
    'paddlex',
    'ocr_engine',
]
try:
    hiddenimports += collect_submodules('paddlex')
    hiddenimports += collect_submodules('paddleocr')
except Exception:
    pass

a = Analysis(
    [os.path.join(BASE_DIR, 'app_window.py')],
    pathex=[BASE_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'notebook', 'pytest', 'IPython'],
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
    name='AnhiuOCR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(BASE_DIR, 'app_icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AnhiuOCR',
)
