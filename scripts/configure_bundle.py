"""Write release metadata without embedding any workspace paths or credentials."""
import plistlib
import sys
from pathlib import Path

app, version, repository = sys.argv[1:]
with Path('SwiftUI/Info.plist').open('rb') as source:
    info = plistlib.load(source)
info['CFBundleShortVersionString'] = version
info['CFBundleVersion'] = version
info['CFBundleDisplayName'] = 'Eagle of the Month'
if repository:
    info['SUFeedURL'] = f'https://github.com/{repository}/releases/latest/download/appcast.xml'
with (Path(app) / 'Contents/Info.plist').open('wb') as destination:
    plistlib.dump(info, destination)
