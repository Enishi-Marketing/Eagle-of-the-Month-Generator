#!/usr/bin/env python3
"""Remove backgrounds from student photos in the Photos/ folder.

Reads every .jpg / .jpeg in Photos/, removes the background using rembg,
and saves the result as a .png with the same base name.
Skips files that already have an up-to-date .png output.

Usage:
    python3 process_photos.py
    python3 process_photos.py --force   # re-process even if PNG already exists

Dependencies:
    pip3 install rembg Pillow
"""

import argparse
from pathlib import Path
from rembg import remove, new_session
from PIL import Image
import io

PHOTO_DIR = Path(__file__).parent / "Photos"

def process(src: Path, session, force: bool = False):
    dst = src.with_suffix(".png")
    if dst.exists() and not force:
        print(f"  Skipping {src.name} (PNG already exists — use --force to redo)")
        return
    print(f"  Processing {src.name} → {dst.name} ...", end=" ", flush=True)
    with open(src, "rb") as f:
        output = remove(f.read(), session=session)
    img = Image.open(io.BytesIO(output)).convert("RGBA")
    img.save(dst)
    print("done")

def main():
    p = argparse.ArgumentParser(description="Remove photo backgrounds")
    p.add_argument("--force", action="store_true",
                   help="Re-process even if output PNG already exists")
    args = p.parse_args()

    photos = sorted(
        f for f in PHOTO_DIR.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg")
    )
    if not photos:
        print("No JPEG photos found in Photos/.")
        return

    print(f"Found {len(photos)} photo(s). Loading model...")
    session = new_session()  # load once, reuse for all photos

    for photo in photos:
        process(photo, session, force=args.force)

    print("All done.")

if __name__ == "__main__":
    main()
