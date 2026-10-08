#!/bin/zsh
set -euo pipefail

# Double-click this file in Finder to build (when needed) and open the app.
PROJECT_DIR="${0:A:h}"
APP_BUNDLE="$PROJECT_DIR/dist/Eagle of the Month.app"
EXECUTABLE="$APP_BUNDLE/Contents/MacOS/EaglePreview"

trap 'echo "Could not open Eagle Preview. See the error above."; read "?Press Return to close…"' ERR
if [[ ! -x "$EXECUTABLE" ]]; then
    "$PROJECT_DIR/scripts/build_macos_app.sh"
fi

# Reuse the running app; LaunchServices gives it a clickable Dock entry.
echo "Opening Eagle Preview…"
open "$APP_BUNDLE" --args --project-root "$PROJECT_DIR"
