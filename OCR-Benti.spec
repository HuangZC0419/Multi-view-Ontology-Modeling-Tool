# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 — OCR 本体建模工具 (Python 3.8 / Win7 兼容)"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# ---------- 基础配置 ----------
APP_NAME = "OCR-Benti"
_PROJ_ROOT = Path(SPECPATH)
ENTRY_SCRIPT = str(_PROJ_ROOT / "backend" / "app" / "main.py")

# ---------- 收集动态库和数据文件 ----------
binaries = []
all_datas = []

# ── VC++ 运行时 + UCRT DLL（conda 环境中的，Win7 必需）──
CONDA_ROOT = Path(os.environ.get("CONDA_PREFIX", sys.prefix))
for dll_name in [
    # VC++ 运行时
    "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll", "msvcp140_codecvt_ids.dll",
    "vcruntime140.dll", "vcruntime140_1.dll",
]:
    dll_path = CONDA_ROOT / dll_name
    if dll_path.is_file():
        binaries.append((str(dll_path), "."))

# UCRT DLL（Win7 上没有，必须打包）
for dll_path in CONDA_ROOT.glob("api-ms-win-crt-*.dll"):
    binaries.append((str(dll_path), "."))
for dll_path in CONDA_ROOT.glob("api-ms-win-core-*.dll"):
    binaries.append((str(dll_path), "."))

# ── onnxruntime 全部 DLL（放到根目录确保能被找到）──
try:
    binaries.extend(collect_dynamic_libs("onnxruntime"))
except Exception:
    pass
try:
    all_datas.extend(collect_data_files("onnxruntime"))
except Exception:
    pass

import onnxruntime as _ort
_ORT_DIR = Path(_ort.__file__).parent
for _p in _ORT_DIR.rglob("*.dll"):
    binaries.append((str(_p), "."))
for _p in _ORT_DIR.rglob("*.pyd"):
    # .pyd 保留包目录结构，确保 Python import 能正确解析
    rel = _p.parent.relative_to(_ORT_DIR.parent.parent)
    binaries.append((str(_p), str(rel)))

# ── rapidocr_onnxruntime 模型文件 ──
try:
    all_datas.extend(collect_data_files("rapidocr_onnxruntime"))
except Exception:
    pass

# ── jieba 词典 ──
try:
    all_datas.extend(collect_data_files("jieba"))
except Exception:
    pass

# ── 前端静态文件 ──
frontend_dist = _PROJ_ROOT / "frontend" / "dist"
if frontend_dist.is_dir():
    for item in frontend_dist.rglob("*"):
        if item.is_file():
            dest = Path("frontend") / "dist" / item.relative_to(frontend_dist)
            all_datas.append((str(item), str(dest.parent)))

# ── 示例图片 ──
test_png = _PROJ_ROOT / "test.png"
if test_png.is_file():
    all_datas.append((str(test_png), "."))

# ── 预置案例项目 ──
for _proj_name in ["machining-demo"]:
    _proj_file = _PROJ_ROOT / "backend" / "projects" / f"{_proj_name}.json"
    if _proj_file.is_file():
        all_datas.append((str(_proj_file), "projects"))

# ── 隐藏导入 ──
hidden_imports = [
    "rapidocr_onnxruntime",
    "onnxruntime",
    "onnxruntime.capi",
    "cv2",
    "jieba",
    "jieba.posseg",
    "jieba.finalseg",
    "numpy",
    "numpy.core._methods",
    "numpy.lib.format",
    "PIL",
    "fastapi",
    "uvicorn",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "pydantic",
    "starlette",
    "shapely",
]

# ── 排除不需要的模块 ──
excluded_modules = [
    "tkinter",
    "unittest",
    "http.server",
    "xmlrpc",
    "pydoc",
    "distutils",
    "test",
    "pip",
    "matplotlib",
    "scipy",
    "pandas",
    "IPython",
    "jupyter",
    "notebook",
    "tornado",
]

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[],
    binaries=binaries,
    datas=all_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
