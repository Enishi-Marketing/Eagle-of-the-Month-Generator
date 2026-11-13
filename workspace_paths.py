"""Resolve private workspace paths without depending on the launch directory."""
from pathlib import Path


def photo_source_path(workspace, configured=None):
    root = Path(workspace).expanduser().resolve()
    if not configured:
        return root / 'Photos'
    path = Path(configured).expanduser()
    return path if path.is_absolute() else root / path
