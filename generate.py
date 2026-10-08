#!/usr/bin/env python3
"""Eagle of the Month Certificate Generator

Reads student data from Spreadsheet/Eagle of the Month.csv and
produces a PDF with one full-page A4 certificate per student.

- Drop a .jpg/.jpeg/.cr3 in Photos/ — background is removed automatically.
- Already-processed .png files are reused as-is (delete the PNG to re-process).
- Certificates print First Name only; Last Name is used for photo matching.

Usage:
    python3 generate.py --month April --year 2026
    python3 generate.py --month May --year 2026 --output my_file.pdf

Dependencies:
    pip3 install PyMuPDF Pillow rembg onnxruntime
"""

import csv
import argparse
import os
import sys
import io
import re
import subprocess
import json
from pathlib import Path

# If an editor terminal runs the system Python, restart inside this project's
# virtual environment before importing project dependencies.
VENV_DIR = Path(__file__).parent / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"
if not getattr(sys, "frozen", False) and VENV_PYTHON.exists() and Path(sys.prefix).resolve() != VENV_DIR.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import fitz  # PyMuPDF
from PIL import Image as PILImage
from PIL import ImageEnhance

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(os.environ.get("EAGLE_WORKSPACE", Path(__file__).parent))
ASSET_DIR  = Path(__file__).parent if getattr(sys, "frozen", False) else BASE_DIR
BG_DIR     = ASSET_DIR / "Backgrounds"
PHOTO_DIR  = BASE_DIR / "Photos"
PHOTO_SOURCE_DIR = Path(
    "/Users/marketing/Library/CloudStorage/GoogleDrive-austin.witt@enishi.ac.jp/"
    "Shared drives/Enishi - Multimedia/04_Events/2025-26/"
    "2026.04.22 - Yearbook Photo Day/Named Photos from Photo Booth"
)
LOGOS_DIR  = ASSET_DIR / "Logos"
TOP_LAYER  = ASSET_DIR / "Top_Layer" / "top.png"
FONT_PATH  = ASSET_DIR / "Fonts" / "TitanOne-Regular.ttf"
CSV_FILE   = BASE_DIR / "Spreadsheet" / "Eagle of the Month.csv"
OUTPUT_DIR = BASE_DIR / "Output"

FONT_LABEL = "titanone"

# ── House → (background file, color, logo file) ───────────────────────────────
HOUSES = {
    "Black Navigators":   ("blackNavigatorsBg.pdf",  (0.08, 0.08, 0.08), "blackNavigators.png"),
    "Blue Divers":        ("blueDiversBg.pdf",        (0.12, 0.28, 0.72), "blueDivers.png"),
    "Brown Screechers":   ("brownScreechersBg.pdf",   (0.38, 0.20, 0.08), "brownScreechers.png"),
    "Green Gliders":      ("greenGlidersBg.pdf",      (0.10, 0.46, 0.18), "greenGliders.png"),
    "Orange Defenders":   ("orangeDefendersBg.pdf",   (0.88, 0.46, 0.02), "orangeDefenders.png"),
    "Pink Perchers":      ("pinkPerchersBg.pdf",      (0.82, 0.38, 0.58), "pinkPerchers.png"),
    "Purple Protectors":  ("purpleProtectorsBg.pdf",  (0.46, 0.08, 0.64), "purpleProtectors.png"),
    "Red Hunters":        ("redHuntersBg.pdf",        (0.78, 0.10, 0.14), "redHunters.png"),
    "Sky Blue Swoopers":  ("skyBlueSwoopersBg.pdf",   (0.32, 0.66, 0.88), "skyBlueSwoopers.png"),
    "Yellow Survivors":   ("yellowSurvivorsBg.pdf",   (0.82, 0.72, 0.02), "yellowSurvivors.png"),
}
DEFAULT_HOUSE = ("greenGlidersBg.pdf", (0.10, 0.46, 0.18), "greenGliders.png")

# ── A4 / certificate dimensions ───────────────────────────────────────────────
A4_W, A4_H = 595.28, 841.89
DESIGN_W = 8.5  / 2.54 * 72   # original single certificate width
DESIGN_H = 12.5 / 2.54 * 72   # original single certificate height
CW, CH = A4_W, A4_H
FULL_PAGE_RECT = fitz.Rect(0, 0, A4_W, A4_H)
LAYOUT_SCALE = CH / DESIGN_H

# ── Layout fractions ──────────────────────────────────────────────────────────
MONTH_Y        = 0.228
STUDENT_H_FRAC = 0.68    # student height as fraction of CH
STUDENT_BOTTOM = 0.910   # student feet baseline (fraction of CH)
NAME_Y         = 0.775
GRADE_Y        = 0.855
HOUSE_Y        = 0.942
MARGIN_X       = 18 * LAYOUT_SCALE

# ── Font sizes ────────────────────────────────────────────────────────────────
MONTH_SIZE = 15 * LAYOUT_SCALE
NAME_SIZE  = 25 * LAYOUT_SCALE
GRADE_SIZE = 14 * LAYOUT_SCALE
HOUSE_SIZE = 13 * LAYOUT_SCALE
LOGO_SIZE  = 47 * LAYOUT_SCALE   # pts — logo square side length on the cert

WHITE = (1.0, 1.0, 1.0)

# ── Lazy rembg session ────────────────────────────────────────────────────────
_rembg_session = None
NON_INTERACTIVE = False

DEFAULT_LAYOUT = {
    "student_scale": 1.0,
    "student_x": 0.0,
    "student_y": 0.0,
    "exposure": 0.0,
    "text_scale": 1.0,
    "text_y": 0.0,
    "show_photos": True,
    "show_logos": True,
    "show_banner": True,
}


def normalized_layout(overrides=None) -> dict:
    """Return safe layout settings shared by the CLI and preview app."""
    layout = DEFAULT_LAYOUT.copy()
    if overrides:
        layout.update({k: v for k, v in overrides.items() if k in layout})
    for key, low, high in (
        ("student_scale", 0.50, 1.40),
        ("student_x", -0.25, 0.25),
        ("student_y", -0.20, 0.20),
        ("exposure", -2.0, 2.0),
        ("text_scale", 0.70, 1.35),
        ("text_y", -0.12, 0.12),
    ):
        try:
            layout[key] = max(low, min(high, float(layout[key])))
        except (TypeError, ValueError):
            layout[key] = DEFAULT_LAYOUT[key]
    for key in ("show_photos", "show_logos", "show_banner"):
        layout[key] = bool(layout[key])
    return layout

def rembg_session():
    global _rembg_session
    if _rembg_session is None:
        from rembg import new_session
        print("  Loading background-removal model (first run only)...")
        _rembg_session = new_session()
    return _rembg_session


# ── Photo helpers ─────────────────────────────────────────────────────────────

PHOTO_EXTS = {".jpeg", ".jpg", ".png", ".cr3"}
RAW_PHOTO_EXTS = {".cr3"}
FILENAME_NOISE = {"large", "medium", "small", "edited", "edit", "copy"}


def _tokens(text: str) -> list:
    return [
        token for token in re.findall(r"[a-z0-9]+", str(text).lower())
        if token not in FILENAME_NOISE
    ]


def _field(row: dict, *names: str) -> str:
    normalized = {str(k).strip().lower(): v for k, v in row.items()}
    for name in names:
        value = normalized.get(name.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def student_first_name(student: dict) -> str:
    return _field(student, "First Name", "First", "Name")


def student_last_name(student: dict) -> str:
    return _field(student, "Last Name", "Last", "Surname", "Family Name")


def _photo_files() -> list:
    dirs = [PHOTO_SOURCE_DIR, PHOTO_DIR]
    files = []
    for directory in dirs:
        if not directory.exists():
            continue
        files.extend(
            p for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in PHOTO_EXTS
        )
    return sorted(files, key=lambda p: p.name.lower())


def _matching_photos(first_name: str, last_name: str) -> list:
    first_tokens = _tokens(first_name)
    last_tokens = _tokens(last_name)
    if not first_tokens:
        return []

    matches = []
    for path in _photo_files():
        file_tokens = _tokens(path.stem)
        if not all(token in file_tokens for token in first_tokens):
            continue
        if _last_name_matches(file_tokens, last_tokens):
            matches.append(path)

    by_name = {}
    for path in matches:
        key = tuple(_tokens(path.stem))
        current = by_name.get(key)
        if current is None or _photo_rank(path) < _photo_rank(current):
            by_name[key] = path
    return sorted(by_name.values(), key=lambda p: p.name.lower())


def _photo_rank(path: Path) -> tuple:
    local_cached = path.parent == PHOTO_DIR and path.suffix.lower() == ".png"
    ext_order = {".png": 0, ".jpg": 1, ".jpeg": 1, ".cr3": 2}
    return (0 if local_cached else 1, ext_order.get(path.suffix.lower(), 9))


def _last_name_matches(file_tokens: list, last_tokens: list) -> bool:
    if not last_tokens:
        return True

    for token in last_tokens:
        if len(token) == 1:
            if not any(file_token.startswith(token) for file_token in file_tokens):
                return False
        elif token not in file_tokens:
            return False
    return True


def _ask_for_photo(student_label: str, matches: list) -> Path:
    if NON_INTERACTIVE:
        if matches:
            print(f"  Note: multiple photos match {student_label}; using {matches[0].name}.")
            return matches[0]
        print(f"  Note: no photo found for {student_label}.")
        return None

    print(f"\nPhoto match needed for {student_label}.")
    if matches:
        print("Multiple possible photos found:")
        for i, path in enumerate(matches, start=1):
            print(f"  {i}. {path}")
        print("Choose a number, paste a different image path, or press Enter to skip.")
    else:
        print("No matching JPEG/PNG/CR3 photo found.")
        print("Paste the image path to use, or press Enter to skip.")

    try:
        choice = input("> ").strip().strip("'\"")
    except EOFError:
        return None

    if not choice:
        return None
    if matches and choice.isdigit():
        index = int(choice) - 1
        if 0 <= index < len(matches):
            return matches[index]

    path = Path(choice).expanduser()
    if path.exists() and path.suffix.lower() in PHOTO_EXTS:
        return path

    print(f"  Note: {choice!r} is not a readable JPEG/PNG/CR3 file.")
    return None


def _resolve_photo_source(student: dict) -> Path:
    first_name = student_first_name(student)
    last_name = student_last_name(student)
    student_label = f"{first_name} {last_name}".strip() or "this student"

    matches = _matching_photos(first_name, last_name)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return _ask_for_photo(student_label, matches)
    return _ask_for_photo(student_label, [])


def _cached_png_path(src: Path) -> Path:
    safe_stem = "_".join(_tokens(src.stem)) or src.stem
    return PHOTO_DIR / f"{safe_stem}.png"


def _cached_jpeg_path(src: Path) -> Path:
    safe_stem = "_".join(_tokens(src.stem)) or src.stem
    return PHOTO_DIR / f"{safe_stem}.jpg"


def _convert_raw_to_jpeg(src: Path) -> Path:
    jpg = _cached_jpeg_path(src)
    if jpg.exists():
        return jpg

    print(f"  Converting RAW photo: {src.name} → {jpg.name}")
    PHOTO_DIR.mkdir(exist_ok=True)
    try:
        import rawpy
        with rawpy.imread(str(src)) as raw:
            rgb = raw.postprocess(use_camera_wb=True)
        PILImage.fromarray(rgb).save(jpg, quality=95)
        return jpg
    except ImportError:
        pass
    except Exception as exc:
        print(f"  Note: Python RAW conversion failed for {src.name}. {exc}")

    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", str(src), "--out", str(jpg)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        print("  Note: cannot convert CR3 because the macOS image tool is unavailable.")
        return None
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip()
        print(f"  Note: could not convert {src.name}. {detail}")
        return None
    return jpg


def get_photo_png(student: dict):
    """Return student's cut-out PNG, asking when filename matching is ambiguous."""
    src = _resolve_photo_source(student)
    if not src:
        return None
    if src.suffix.lower() == ".png":
        return src
    if src.suffix.lower() in RAW_PHOTO_EXTS:
        src = _convert_raw_to_jpeg(src)
        if not src:
            return None

    png = _cached_png_path(src)
    if png.exists():
        return png

    print(f"  Removing background: {src.name} → {png.name}")
    from rembg import remove
    output = remove(src.read_bytes(), session=rembg_session())
    img = PILImage.open(io.BytesIO(output)).convert("RGBA")
    img.save(png)
    return png



def crop_to_subject(png_path: Path) -> PILImage.Image:
    """Crop the image tightly around non-transparent pixels (the student)."""
    img = PILImage.open(png_path).convert("RGBA")
    bbox = img.split()[3].getbbox()   # alpha-channel bounding box
    if not bbox:
        return img
    l, t, r, b = bbox
    # 3 % padding so we don't clip hair/shoes
    px, py = (r - l) * 0.03, (b - t) * 0.03
    bbox_padded = (
        max(0,          int(l - px)),
        max(0,          int(t - py)),
        min(img.width,  int(r + px)),
        min(img.height, int(b + py)),
    )
    return img.crop(bbox_padded)


def place_student(page: fitz.Page, cert_rect: fitz.Rect, png_path: Path, layout: dict):
    """Scale student to target height and center them on the right side of cert."""
    student = crop_to_subject(png_path)
    if layout["exposure"] != 0:
        # Exposure is expressed in photographic stops: +1 EV doubles light.
        alpha = student.getchannel("A")
        rgb = student.convert("RGB")
        rgb = ImageEnhance.Brightness(rgb).enhance(2.0 ** layout["exposure"])
        student = rgb.convert("RGBA")
        student.putalpha(alpha)
    sw, sh  = student.size
    aspect  = sw / sh

    # Scale to target height, then clamp to 88 % of cert width
    target_h = CH * STUDENT_H_FRAC * layout["student_scale"]
    target_w = target_h * aspect
    if target_w > cert_rect.width * 0.88:
        target_w = cert_rect.width * 0.88
        target_h = target_w / aspect

    # Vertical: feet sit at STUDENT_BOTTOM
    bottom_y = cert_rect.y0 + CH * (STUDENT_BOTTOM + layout["student_y"])
    top_y    = bottom_y - target_h

    # Horizontal: centre the student in the right 60 % of the cert
    area_start = cert_rect.x0 + cert_rect.width * 0.40
    cx = area_start + (cert_rect.x1 - area_start) / 2 + cert_rect.width * layout["student_x"]
    left_x  = max(cert_rect.x0, cx - target_w / 2)
    right_x = min(cert_rect.x1, left_x + target_w)

    # Keep enough pixels for a crisp 300 dpi print, but do not embed the often
    # enormous original cut-out. This makes previews and final PDFs far smaller.
    print_scale = 300 / 72
    max_pixel_w = max(1, int((right_x - left_x) * print_scale))
    max_pixel_h = max(1, int((bottom_y - top_y) * print_scale))
    if student.width > max_pixel_w or student.height > max_pixel_h:
        student.thumbnail((max_pixel_w, max_pixel_h), PILImage.Resampling.LANCZOS)

    buf = io.BytesIO()
    student.save(buf, format="PNG")
    page.insert_image(
        fitz.Rect(left_x, top_y, right_x, bottom_y),
        stream=buf.getvalue(),
        keep_proportion=False,   # rect is already the correct aspect ratio
    )


# ── Logo helper ───────────────────────────────────────────────────────────────

_logo_cache: dict = {}

def logo_stream(logo_file: str) -> bytes:
    """Load logo PNG, strip white background, return PNG bytes (cached)."""
    if logo_file in _logo_cache:
        return _logo_cache[logo_file]
    path = LOGOS_DIR / logo_file
    if not path.exists():
        return None
    img = PILImage.open(path).convert("RGBA")
    data = [(r, g, b, 0 if (r > 235 and g > 235 and b > 235) else a)
            for r, g, b, a in img.getdata()]
    img.putdata(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = buf.getvalue()
    _logo_cache[logo_file] = result
    return result


def draw_logo(page: fitz.Page, cert_rect: fitz.Rect, logo_file: str, scale: float = 1.0):
    """Draw house logo in the top-left corner, just below the month text."""
    stream = logo_stream(logo_file)
    if not stream:
        return
    size = LOGO_SIZE * scale
    left = cert_rect.x0 + 8 + size * 0.25
    top  = cert_rect.y0 + CH * 0.265 - size
    page.insert_image(fitz.Rect(left, top, left + size, top + size),
                      stream=stream, keep_proportion=True)


# ── Text helpers ──────────────────────────────────────────────────────────────

def font_width(text: str, size: float) -> float:
    return fitz.Font(fontfile=str(FONT_PATH)).text_length(text, fontsize=size)


def center_x(text: str, size: float, rect: fitz.Rect) -> float:
    return rect.x0 + (rect.width - font_width(text, size)) / 2


def shadow_text(page, pt, text, size, fill=WHITE, shadow=(0.0, 0.0, 0.15)):
    page.insert_text((pt[0] + 1.5, pt[1] + 1.5), text,
                     fontfile=str(FONT_PATH), fontname=FONT_LABEL,
                     fontsize=size, color=shadow)
    page.insert_text(pt, text,
                     fontfile=str(FONT_PATH), fontname=FONT_LABEL,
                     fontsize=size, color=fill)


def draw_bottom_label(page, rect, label, layout):
    available_w = rect.width * 0.72
    size = HOUSE_SIZE * layout["text_scale"]
    while font_width(label, size + 1) < available_w and size < 40:
        size += 1
    shadow_text(page,
                (center_x(label, size, rect), rect.y0 + CH * (HOUSE_Y + layout["text_y"])),
                label, size)


# ── Certificate drawing ───────────────────────────────────────────────────────

def draw_certificate(page: fitz.Page, rect: fitz.Rect, student: dict, layout=None):
    layout = normalized_layout(layout)
    house = student.get("House", "").strip()
    name  = student_first_name(student)
    last_name = student_last_name(student)
    student_label = f"{name} {last_name}".strip() or name

    if not house:
        print(f"  Note: no house for {student_label}, using default.")

    # 1. House background
    bg_file, _, logo_file = HOUSES.get(house, DEFAULT_HOUSE)
    bg_path = BG_DIR / bg_file
    if not bg_path.exists():
        bg_path = BG_DIR / DEFAULT_HOUSE[0]
    bg_doc = fitz.open(str(bg_path))
    page.show_pdf_page(rect, bg_doc, 0)
    bg_doc.close()

    # 2. Top layer ("EAGLE OF THE MONTH" banner)
    if layout["show_banner"]:
        page.insert_image(rect, filename=str(TOP_LAYER), keep_proportion=False)

    # 3. Student photo — auto-processed and smart-placed
    if layout["show_photos"]:
        png = get_photo_png(student)
        if png:
            place_student(page, rect, png, layout)
        else:
            print(f"  Note: no photo for {student_label}.")

    # 4. Text overlays
    month = student["Month"].strip().upper()
    text_scale = layout["text_scale"]
    text_y = layout["text_y"]
    month_size = MONTH_SIZE * text_scale
    name_size = NAME_SIZE * text_scale
    grade_size = GRADE_SIZE * text_scale
    shadow_text(page, (center_x(month, month_size, rect), rect.y0 + CH * (MONTH_Y + text_y)),
                month, month_size)
    shadow_text(page, (rect.x0 + MARGIN_X, rect.y0 + CH * (NAME_Y + text_y)), name, name_size)
    shadow_text(page, (rect.x0 + MARGIN_X, rect.y0 + CH * (GRADE_Y + text_y)),
                student["Grade"].strip(), grade_size)
    draw_bottom_label(page, rect, house.upper() if house else "—", layout)

    # 5. House logo — bottom-right corner
    if logo_file and layout["show_logos"]:
        draw_logo(page, rect, logo_file, text_scale)


# ── Main ──────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    config_path = BASE_DIR / "config.json"
    if config_path.exists():
        import json
        return json.loads(config_path.read_text())
    return {}


def load_students(month: str, year: str,
                  sheet_id: str = None, sheet_name: str = None,
                  local_csv: bool = False) -> list:
    config = _load_config()

    # CLI arg overrides config; config overrides CSV fallback
    resolved_id   = None if local_csv else sheet_id   or config.get("sheet_url")
    resolved_name = None if local_csv else sheet_name or config.get("sheet_name")

    if resolved_id and resolved_id != "YOUR_GOOGLE_SHEET_URL_HERE":
        from gsheets import read_sheet
        print("  Fetching from Google Sheets...")
        all_rows = read_sheet(resolved_id, sheet_name=resolved_name)
    else:
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            all_rows = list(csv.DictReader(f))

    return [
        r for r in all_rows
        if (str(r.get("Month", "")).strip().lower() == month.lower()
            and str(r.get("Year", "")).strip() == str(year))
    ]


def generate(month: str, year: str, output_path: Path,
             sheet_id: str = None, sheet_name: str = None,
             local_csv: bool = False, layout=None):
    students = load_students(
        month,
        year,
        sheet_id=sheet_id,
        sheet_name=sheet_name,
        local_csv=local_csv,
    )
    if not students:
        print(f"No students found for {month} {year}. Check the CSV.")
        sys.exit(0)

    print(f"Generating {len(students)} certificate(s) for {month} {year}.")
    OUTPUT_DIR.mkdir(exist_ok=True)

    out = fitz.open()
    for student in students:
        out_page = out.new_page(width=A4_W, height=A4_H)
        draw_certificate(out_page, FULL_PAGE_RECT, student, layout)

    out.save(str(output_path), garbage=4, deflate=True)
    out.close()
    print(f"Saved → {output_path}")


def main():
    global PHOTO_SOURCE_DIR, NON_INTERACTIVE

    p = argparse.ArgumentParser(description="Eagle of the Month Certificate Generator")
    p.add_argument("--month",      required=True,
                   help="Month name, e.g. May")
    p.add_argument("--year",       required=True,
                   help="Year, e.g. 2026")
    p.add_argument("--sheet-id",   default=None,
                   help="Google Sheets ID or URL (omit to use local CSV)")
    p.add_argument("--sheet-name", default=None,
                   help="Tab name in the workbook (default: first tab)")
    p.add_argument("--local-csv", action="store_true",
                   help="Read Spreadsheet/Eagle of the Month.csv instead of Google Sheets")
    p.add_argument("--photo-source-dir", default=str(PHOTO_SOURCE_DIR),
                   help="Folder containing named student photos")
    p.add_argument("--output",     default=None,
                   help="Output PDF (default: Output/eagle_<Month>_<Year>.pdf)")
    p.add_argument("--layout-json", default=None,
                   help="JSON object with preview/editor layout settings")
    p.add_argument("--non-interactive", action="store_true",
                   help="Never prompt for photo choices (used by the preview app)")
    args = p.parse_args()

    PHOTO_SOURCE_DIR = Path(args.photo_source_dir).expanduser()
    NON_INTERACTIVE = args.non_interactive

    try:
        layout = normalized_layout(json.loads(args.layout_json)) if args.layout_json else None
    except json.JSONDecodeError as exc:
        p.error(f"--layout-json is not valid JSON: {exc}")

    out_path = (
        Path(args.output) if args.output
        else OUTPUT_DIR / f"eagle_{args.month}_{args.year}.pdf"
    )
    generate(args.month, args.year, out_path,
             sheet_id=args.sheet_id, sheet_name=args.sheet_name,
             local_csv=args.local_csv, layout=layout)


if __name__ == "__main__":
    main()
