"""Fail publication if a source list or app archive contains workspace data."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

PRIVATE_DIRS = {'photos', 'spreadsheet', 'output', '.venv'}
PRIVATE_NAMES = {'config.json', 'credentials.json'}

def check_name(name):
    path = Path(name)
    if PRIVATE_DIRS.intersection(part.lower() for part in path.parts):
        raise SystemExit(f'Private workspace directory detected: {name}')
    if path.name.lower() in PRIVATE_NAMES:
        raise SystemExit(f'Private configuration detected: {name}')

def check_json(name, contents):
    if name.endswith('.json'):
        try:
            value = json.loads(contents)
        except (ValueError, UnicodeError):
            return
        if isinstance(value, dict) and ('private_key' in value or value.get('type') == 'service_account'):
            raise SystemExit(f'Credentials detected: {name}')

if len(sys.argv) == 1:
    names = subprocess.check_output(['git', 'ls-files', '-z']).decode().split('\0')
    for name in filter(None, names):
        check_name(name)
        if name.endswith('.json'):
            check_json(name, Path(name).read_bytes())
    print('Tracked source contains no photos, spreadsheet data, output PDFs, or credentials.')
else:
    target = Path(sys.argv[1])
    if target.is_dir():
        for file in target.rglob('*'):
            name = str(file.relative_to(target))
            check_name(name)
            if file.is_file() and not file.is_symlink() and file.suffix == '.json':
                check_json(name, file.read_bytes())
    else:
        with zipfile.ZipFile(target) as archive:
            for name in archive.namelist():
                check_name(name)
                if name.endswith('.json'):
                    check_json(name, archive.read(name))
    print('Release contains no photos, spreadsheet data, output PDFs, or credentials.')
