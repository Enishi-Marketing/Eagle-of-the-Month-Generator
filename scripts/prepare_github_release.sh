#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
SPARKLE_ROOT="${SPARKLE_ROOT:-$ROOT/.build/Sparkle}"
RELEASE_REPOSITORY="${RELEASE_REPOSITORY:-$(tr -d '[:space:]' < RELEASE_REPOSITORY)}"
[[ "$RELEASE_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || exit 1
VERSION="$(tr -d '[:space:]' < VERSION)"
APP="$ROOT/dist/Eagle of the Month.app"
FEED="$(/usr/libexec/PlistBuddy -c 'Print :SUFeedURL' "$APP/Contents/Info.plist")"
[[ "$FEED" == "https://github.com/$RELEASE_REPOSITORY/releases/latest/download/appcast.xml" ]] || { echo 'Rebuild for the matching release repository.'; exit 1; }
[[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$APP/Contents/Info.plist")" == "$VERSION" ]] || { echo 'Rebuild for the current VERSION.'; exit 1; }
codesign --verify --deep --strict "$APP"
"${PYTHON_BIN:-.venv/bin/python}" scripts/audit_private_data.py "$APP"
STAGE="$ROOT/.build/github-release/$VERSION"
if [[ -d "$STAGE" ]]; then
    mv "$STAGE" "$STAGE.previous.$(date +%Y%m%d%H%M%S)"
fi
mkdir -p "$STAGE"
ARCHIVE="Eagle.of.the.Month.v${VERSION}.zip"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$STAGE/$ARCHIVE"
"${PYTHON_BIN:-.venv/bin/python}" scripts/audit_private_data.py "$STAGE/$ARCHIVE"
(cd "$STAGE" && shasum -a 256 "$ARCHIVE" > "$ARCHIVE.sha256")
"$SPARKLE_ROOT/bin/generate_appcast" \
    --account jp.ac.enishi.eagle-preview \
    --download-url-prefix "https://github.com/$RELEASE_REPOSITORY/releases/download/v$VERSION/" \
    --maximum-deltas 0 -o "$STAGE/appcast.xml" "$STAGE"
echo "Signed release assets: $STAGE"
