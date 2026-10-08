#!/usr/bin/env python3
"""Project-neutral Google Sheets reader.

Drop this file into any project and import it:

    from gsheets import read_sheet

    rows = read_sheet("https://docs.google.com/spreadsheets/d/SHEET_ID/...")
    rows = read_sheet("SHEET_ID", sheet_name="May 2026")
    rows = read_sheet("SHEET_ID")          # reads first tab

Returns a list of dicts — same shape as csv.DictReader — so you can swap
this in wherever you currently read a CSV.

────────────────────────────────────────────────────────────────────────────
ONE-TIME SETUP (do this once; credentials work across all your projects)
────────────────────────────────────────────────────────────────────────────
1. Go to https://console.cloud.google.com
   • Create a project (or reuse one)
   • Enable the "Google Sheets API"

2. Create a Service Account
   • IAM & Admin → Service Accounts → Create
   • Role: not required (leave blank)
   • Done

3. Download credentials
   • Click the service account → Keys tab → Add Key → JSON
   • Save the file to:  ~/.config/gsheets/credentials.json

4. Share your Google Sheet with the service account
   • Open the JSON — copy the "client_email" value
   • Open your Sheet → Share → paste that email (Viewer is enough)

That's it. Any script that imports this module will authenticate automatically.
────────────────────────────────────────────────────────────────────────────

Dependencies:
    pip3 install gspread google-auth
"""

from pathlib import Path

import json as _json

# Named locations checked first; if not found, any service-account JSON in cwd is used.
_NAMED_PATHS = [
    Path.cwd() / "credentials.json",
    Path.home() / ".config" / "gsheets" / "credentials.json",
]


def _find_credentials() -> Path:
    # 1. Check well-known named paths
    for p in _NAMED_PATHS:
        if p.exists():
            return p

    # 2. Scan cwd for any JSON that looks like a service account key
    for p in sorted(Path.cwd().glob("*.json")):
        try:
            data = _json.loads(p.read_text())
            if data.get("type") == "service_account":
                return p
        except Exception:
            continue

    raise FileNotFoundError(
        "Google Sheets credentials not found.\n"
        "Place your service-account JSON in the project folder "
        "or at ~/.config/gsheets/credentials.json.\n"
        "See the setup instructions at the top of gsheets.py."
    )


def _parse_sheet_id(id_or_url: str) -> str:
    """Accept either a bare sheet ID or a full Google Sheets URL."""
    if "spreadsheets/d/" in id_or_url:
        return id_or_url.split("spreadsheets/d/")[1].split("/")[0]
    return id_or_url.strip()


def read_sheet(
    spreadsheet_id: str,
    sheet_name: str = None,
    sheet_index: int = 0,
) -> list:
    """Read a Google Sheet tab and return rows as a list of dicts.

    Args:
        spreadsheet_id: Bare sheet ID or full Google Sheets URL.
        sheet_name:     Tab name to read (e.g. "May 2026"). If omitted,
                        reads the tab at sheet_index.
        sheet_index:    Zero-based tab index used when sheet_name is None.

    Returns:
        List of dicts with column headers as keys — identical shape to
        csv.DictReader output.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError("Run:  pip3 install gspread google-auth")

    creds = Credentials.from_service_account_file(
        str(_find_credentials()),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    client = gspread.authorize(creds)

    sheet_id = _parse_sheet_id(spreadsheet_id)
    try:
        # Works with a bare ID or full URL
        workbook = client.open_by_key(sheet_id)
    except Exception:
        try:
            # Fall back to opening by title (requires Drive API enabled in Cloud Console)
            workbook = client.open(spreadsheet_id)
        except Exception:
            raise RuntimeError(
                f"Could not open spreadsheet: {spreadsheet_id!r}\n\n"
                "Use the full URL or the ID from the URL:\n"
                "  https://docs.google.com/spreadsheets/d/<ID>/edit\n\n"
                "If using a title, make sure the Google Drive API is enabled\n"
                "in your Cloud Console project."
            )
    worksheet = (
        workbook.worksheet(sheet_name)
        if sheet_name
        else workbook.get_worksheet(sheet_index)
    )

    return worksheet.get_all_records()


def list_sheets(spreadsheet_id: str) -> list:
    """Return the tab names in a workbook — handy for debugging."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError("Run:  pip3 install gspread google-auth")

    creds = Credentials.from_service_account_file(
        str(_find_credentials()),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    client   = gspread.authorize(creds)
    workbook = client.open_by_key(_parse_sheet_id(spreadsheet_id))
    return [ws.title for ws in workbook.worksheets()]
