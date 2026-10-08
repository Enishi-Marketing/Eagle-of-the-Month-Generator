#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
SPARKLE_ROOT="${SPARKLE_ROOT:-$ROOT/.build/Sparkle}"
VERSION="$(tr -d '[:space:]' < VERSION)"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Invalid VERSION'; exit 1; }
RELEASE_REPOSITORY="${RELEASE_REPOSITORY:-}"
if [[ -z "$RELEASE_REPOSITORY" && -f RELEASE_REPOSITORY ]]; then
    RELEASE_REPOSITORY="$(tr -d '[:space:]' < RELEASE_REPOSITORY)"
fi
[[ -z "$RELEASE_REPOSITORY" || "$RELEASE_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || exit 1
if [[ ! -d "$SPARKLE_ROOT/Sparkle.xcframework" ]]; then
    echo 'Fetching Sparkle 2.10.0…'
    mkdir -p "$SPARKLE_ROOT"
    curl --fail --location --retry 3 https://github.com/sparkle-project/Sparkle/releases/download/2.10.0/Sparkle-2.10.0.tar.xz -o "$ROOT/.build/Sparkle-2.10.0.tar.xz"
    tar -xf "$ROOT/.build/Sparkle-2.10.0.tar.xz" -C "$SPARKLE_ROOT"
fi
FRAMEWORK="$SPARKLE_ROOT/Sparkle.xcframework/macos-arm64_x86_64/Sparkle.framework"
APP_PATH="$ROOT/dist/Eagle of the Month.app"
if [[ -d "$APP_PATH" ]]; then
    mv "$APP_PATH" "$ROOT/dist/Eagle of the Month.previous.$(date +%Y%m%d%H%M%S).app"
fi
mkdir -p "$APP_PATH/Contents/MacOS" "$APP_PATH/Contents/Resources" "$APP_PATH/Contents/Frameworks" "$ROOT/.build/ModuleCache"
export SWIFT_MODULECACHE_PATH="$ROOT/.build/ModuleCache"
export CLANG_MODULE_CACHE_PATH="$ROOT/.build/ModuleCache"
export PYINSTALLER_CONFIG_DIR="$ROOT/.pyinstaller"
"$PYTHON_BIN" -m PyInstaller EagleBackend.spec --noconfirm --clean --workpath .build/pyinstaller
ditto "$ROOT/dist/EagleBackend" "$APP_PATH/Contents/Resources/backend"
ditto "$FRAMEWORK" "$APP_PATH/Contents/Frameworks/Sparkle.framework"
xcrun swiftc -O -parse-as-library SwiftUI/EaglePreviewApp.swift \
    -target "$(uname -m)-apple-macosx15.0" \
    -F "$(dirname "$FRAMEWORK")" -framework Sparkle -framework SwiftUI -framework AppKit -framework PDFKit \
    -Xlinker -rpath -Xlinker '@executable_path/../Frameworks' \
    -o "$APP_PATH/Contents/MacOS/EaglePreview"
xcrun swift SwiftUI/MakeAppIcon.swift "$ROOT/.build/AppIcon.iconset"
iconutil -c icns "$ROOT/.build/AppIcon.iconset" -o "$APP_PATH/Contents/Resources/AppIcon.icns"
"$PYTHON_BIN" scripts/configure_bundle.py "$APP_PATH" "$VERSION" "$RELEASE_REPOSITORY"
if [[ "${CODESIGN_IDENTITY:--}" == '-' ]]; then
    codesign --force --deep --sign - "$APP_PATH"
else
    codesign --force --deep --options runtime --timestamp --sign "$CODESIGN_IDENTITY" "$APP_PATH"
fi
codesign --verify --deep --strict "$APP_PATH"
echo "Built $APP_PATH"
if [[ -z "$RELEASE_REPOSITORY" ]]; then
    echo 'Local build ready. Set RELEASE_REPOSITORY before preparing a signed GitHub release.'
fi
