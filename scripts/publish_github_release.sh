#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
RELEASE_REPOSITORY="${RELEASE_REPOSITORY:-$(tr -d '[:space:]' < RELEASE_REPOSITORY)}"
VERSION="$(tr -d '[:space:]' < VERSION)"
command -v gh >/dev/null || { echo 'Install GitHub CLI and run gh auth login first.'; exit 1; }
gh auth status
STAGE="$PWD/.build/github-release/$VERSION"
[[ -f "$STAGE/appcast.xml" ]] || { echo 'Prepare the signed release assets first.'; exit 1; }
"${PYTHON_BIN:-.venv/bin/python}" scripts/audit_private_data.py
"${PYTHON_BIN:-.venv/bin/python}" scripts/audit_private_data.py "$STAGE/Eagle.of.the.Month.v$VERSION.zip"
gh release create "v$VERSION" --repo "$RELEASE_REPOSITORY" \
    --title "Eagle of the Month $VERSION" --notes-file RELEASE_NOTES.md \
    "$STAGE/Eagle.of.the.Month.v$VERSION.zip" \
    "$STAGE/Eagle.of.the.Month.v$VERSION.zip.sha256" "$STAGE/appcast.xml"
