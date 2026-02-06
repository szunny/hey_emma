# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Hey Emma macOS app bundle.

Uses the lightweight OnnxEmbedder at runtime — no torch or
sentence_transformers needed in the bundle.
"""

import os
import sys
from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).parent
RESOURCES = PROJECT_ROOT / "resources"

# --- Collect native libraries and data ---
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files, collect_all

binaries = []
datas = []
hiddenimports_extra = []

# Packages with native extensions that need collecting.
# NOTE: sentence_transformers / transformers / torch are NOT collected —
# the bundled app uses emma.embeddings.OnnxEmbedder directly.
for pkg in ["pvporcupine", "pvrecorder", "onnxruntime", "chromadb",
            "tokenizers", "openwakeword", "sklearn", "scipy"]:
    try:
        _datas, _binaries, _hiddenimports = collect_all(pkg)
        datas += _datas
        binaries += _binaries
        hiddenimports_extra += _hiddenimports
    except Exception as e:
        print(f"WARNING: collect_all({pkg!r}) failed: {e}")

# Bundle resources
datas += [
    (str(PROJECT_ROOT / "commands.yaml"), "resources"),
    (str(PROJECT_ROOT / "Hey-Emma_de_mac_v3_0_0.ppn"), "resources"),
    (str(PROJECT_ROOT / "porcupine_params_de.pv"), "resources"),
    (str(PROJECT_ROOT / "hey_emma.onnx"), "resources"),
]

# ONNX model (required for bundled app)
onnx_model_dir = RESOURCES / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
if onnx_model_dir.exists():
    datas += [(str(onnx_model_dir), "resources/models/paraphrase-multilingual-MiniLM-L12-v2")]
else:
    print("WARNING: ONNX model not found — run 'python packaging/export_model.py' first")

# --- Hidden imports ---
hiddenimports = hiddenimports_extra + [
    # PyObjC
    "AppKit",
    "Foundation",
    "objc",
    "PyObjCTools",
    "PyObjCTools.AppHelper",
    "Speech",
    "AVFoundation",
    "ServiceManagement",
    "pyobjc_framework_Cocoa",
    "pyobjc_framework_Speech",
    "pyobjc_framework_AVFoundation",
    "pyobjc_framework_ServiceManagement",
    # emma modules
    "emma",
    "emma.actions",
    "emma.commands",
    "emma.config",
    "emma.embeddings",
    "emma.main",
    "emma.menubar",
    "emma.stt",
    "emma.tts",
    "emma.wake_word",
    "emma.wake_word_base",
    "emma.wake_word_oww",
    "emma.wake_word_porcupine",
    # ML / embeddings (lightweight)
    "onnxruntime",
    "tokenizers",
    # openWakeWord
    "openwakeword",
    "openwakeword.model",
    "openwakeword.utils",
    # ChromaDB
    "chromadb",
    "chromadb.api",
    "chromadb.config",
    # Misc
    "yaml",
    "dotenv",
    "psutil",
    "docker",
]

# --- Excludes ---
# sentence_transformers / transformers / torch are excluded because the bundled
# app uses emma.embeddings.OnnxEmbedder (onnxruntime + tokenizers only).
excludes = [
    "torch",
    "torchvision",
    "torchaudio",
    "sentence_transformers",
    "transformers",
    "huggingface_hub",
    "safetensors",
    "datasets",
    "accelerate",
    "matplotlib",
    "PIL",
    "tkinter",
    "pytest",
    "pip",
]

a = Analysis(
    [str(PROJECT_ROOT / "emma" / "menubar.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Hey Emma",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch="arm64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Hey Emma",
)

app = BUNDLE(
    coll,
    name="Hey Emma.app",
    icon=str(PROJECT_ROOT / "resources" / "hey_emma.icns") if (PROJECT_ROOT / "resources" / "hey_emma.icns").exists() else None,
    bundle_identifier="com.dentiscribe.hey-emma",
    info_plist={
        "CFBundleName": "Hey Emma",
        "CFBundleDisplayName": "Hey Emma",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSMinimumSystemVersion": "13.0",
        "NSMicrophoneUsageDescription": "Hey Emma benötigt Zugriff auf das Mikrofon für die Spracherkennung und Wake-Word-Erkennung.",
        "NSSpeechRecognitionUsageDescription": "Hey Emma nutzt die Apple Spracherkennung für die Verarbeitung von Sprachbefehlen.",
        "LSUIElement": True,  # No dock icon (background app)
    },
)
