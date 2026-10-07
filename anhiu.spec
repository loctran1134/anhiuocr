# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import glob
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

BASE_DIR = os.path.abspath(SPECPATH)

# 1. Gom các file dữ liệu cần thiết (Model, Config, Icon)
datas = [
    (os.path.join(BASE_DIR, 'requirements.txt'), '.'),
    (os.path.join(BASE_DIR, 'app_icon.ico'), '.'),
]

models_dir = os.path.join(BASE_DIR, 'models')
if os.path.exists(models_dir):
    datas.append((models_dir, 'models'))

# 2. Gom các DLL của PyTorch và Paddle động để khắc phục triệt để WinError 127
binaries = []

try:
    import torch
    torch_lib_dir = os.path.join(os.path.dirname(torch.__file__), 'lib')
    if os.path.exists(torch_lib_dir):
        for dll_file in glob.glob(os.path.join(torch_lib_dir, '*.dll')):
            binaries.append((dll_file, '.'))
            binaries.append((dll_file, 'torch/lib'))
except Exception:
    pass

try:
    import paddle
    paddle_libs_dir = os.path.join(os.path.dirname(paddle.__file__), 'libs')
    if os.path.exists(paddle_libs_dir):
        for dll_file in glob.glob(os.path.join(paddle_libs_dir, '*.dll')):
            binaries.append((dll_file, '.'))
            binaries.append((dll_file, 'paddle/libs'))
except Exception:
    pass

# 3. Thu thập toàn bộ submodules của ONNX Runtime, RapidOCR, PaddleOCR, VietOCR, PyTorch
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
    'onnxruntime',
    'rapidocr_onnxruntime',
    'paddle',
    'paddleocr',
    'paddlex',
    'vietocr',
    'torch',
    'torchvision',
    'yaml',
    'PIL',
    'ocr_engine',
]
try:
    hiddenimports += collect_submodules('rapidocr_onnxruntime')
    hiddenimports += collect_submodules('onnxruntime')
    hiddenimports += collect_submodules('vietocr')
    hiddenimports += collect_submodules('paddleocr')
    hiddenimports += collect_submodules('paddlex')
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
    excludes=['tkinter', 'notebook', 'pytest', 'IPython'],
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
