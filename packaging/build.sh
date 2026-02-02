#!/usr/bin/env bash
set -euo pipefail

# ─── Hey Emma Build Script ──────────────────────────────────────────
# Builds: ONNX model export → PyInstaller .app → .pkg installer
# Usage: bash packaging/build.sh
# ────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION="0.1.0"

cd "$PROJECT_ROOT"

echo "=== Hey Emma Build v${VERSION} ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# ─── Step 1: Export ONNX model (if not already done) ───────────────
MODEL_DIR="resources/models/paraphrase-multilingual-MiniLM-L12-v2"
if [ ! -d "$MODEL_DIR" ]; then
    echo "--- Step 1: Exporting ONNX model ---"
    python packaging/export_model.py
    echo ""
else
    echo "--- Step 1: ONNX model already exported, skipping ---"
    echo ""
fi

# ─── Step 2: Copy resources ───────────────────────────────────────
echo "--- Step 2: Preparing resources ---"
# Porcupine models and commands.yaml stay in project root,
# PyInstaller spec references them directly.
echo "Resources ready."
echo ""

# ─── Step 3: Generate placeholder icon (if missing) ──────────────
if [ ! -f "resources/hey_emma.icns" ]; then
    echo "--- Step 3: Generating placeholder icon ---"
    python3 -c "
import struct, zlib, os, shutil

def create_png(size):
    w = h = size
    rows = []
    cx, cy = w/2, h/2
    r = w * 0.4
    for y in range(h):
        row = b'\x00'
        for x in range(w):
            dx, dy = x-cx, y-cy
            dist = (dx*dx + dy*dy) ** 0.5
            if dist < r:
                t = dist/r
                R = int(120*(1-t) + 60*t)
                G = int(50*(1-t) + 120*t)
                B = int(200*(1-t) + 220*t)
                row += struct.pack('BBBB', R, G, B, 255)
            else:
                row += b'\x00\x00\x00\x00'
        rows.append(row)
    raw = b''.join(rows)
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')

iconset = 'resources/hey_emma.iconset'
os.makedirs(iconset, exist_ok=True)
for sz, nm in [(16,'icon_16x16.png'),(32,'icon_16x16@2x.png'),(32,'icon_32x32.png'),(64,'icon_32x32@2x.png'),(128,'icon_128x128.png'),(256,'icon_128x128@2x.png'),(256,'icon_256x256.png'),(512,'icon_256x256@2x.png'),(512,'icon_512x512.png'),(1024,'icon_512x512@2x.png')]:
    open(os.path.join(iconset, nm), 'wb').write(create_png(sz))
os.system(f'iconutil -c icns -o resources/hey_emma.icns \"{iconset}\"')
shutil.rmtree(iconset)
"
    echo "Icon generated."
    echo ""
else
    echo "--- Step 3: Icon exists, skipping ---"
    echo ""
fi

# ─── Step 4: PyInstaller build ────────────────────────────────────
echo "--- Step 4: Building .app with PyInstaller ---"

# Ensure PyInstaller is available in the current venv
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller in venv..."
    uv pip install "pyinstaller>=6.0"
fi

# Use python -m PyInstaller to ensure it runs within the active venv
# (a bare 'pyinstaller' may point to a system install that can't see venv packages)
python -m PyInstaller --clean --noconfirm packaging/hey_emma.spec
echo ""

# Verify app was created
if [ ! -d "dist/Hey Emma.app" ]; then
    echo "ERROR: dist/Hey Emma.app was not created!"
    exit 1
fi

# Ad-hoc codesign all binaries (fixes AMFI warnings for .so/.dylib files)
echo "Signing app bundle..."
codesign --force --deep --sign - "dist/Hey Emma.app"
echo ".app bundle created: dist/Hey Emma.app"
echo ""

# ─── Step 5: Build .pkg installer ────────────────────────────────
echo "--- Step 5: Building .pkg installer ---"

PKG_ROOT="$(mktemp -d)"
mkdir -p "$PKG_ROOT/Applications"
cp -R "dist/Hey Emma.app" "$PKG_ROOT/Applications/"

# Component package
pkgbuild \
    --root "$PKG_ROOT" \
    --identifier "com.dentiscribe.hey-emma" \
    --version "$VERSION" \
    --install-location "/" \
    --scripts "packaging/scripts" \
    "dist/HeyEmma-component.pkg"

# Product archive with distribution.xml
productbuild \
    --distribution "packaging/distribution.xml" \
    --package-path "dist" \
    --resources "resources" \
    "dist/HeyEmma-${VERSION}.pkg"

# Clean up
rm -f "dist/HeyEmma-component.pkg"
rm -rf "$PKG_ROOT"

echo ""
echo "=== Build complete ==="
echo "  App: dist/Hey Emma.app"
echo "  Installer: dist/HeyEmma-${VERSION}.pkg"
