"""
Shared helpers for the Appointment Date column.

The column is stored in Google Sheets as DD/MM/YYYY text. Older rows written
before this format change are still ISO (YYYY-MM-DD), so every parser here
accepts both.
"""

import pandas as pd
from datetime import date, datetime

DISPLAY_FMT = "%d/%m/%Y"
_KNOWN_FORMATS = (DISPLAY_FMT, "%Y-%m-%d")


def format_appt_date(d) -> str:
    """Format a date/datetime as DD/MM/YYYY for writing to Google Sheets."""
    if isinstance(d, (date, datetime)):
        return d.strftime(DISPLAY_FMT)
    return str(d)


def parse_appt_date(value):
    """Parse a single Appointment Date cell into a date object, or None.
    Accepts both DD/MM/YYYY (current) and YYYY-MM-DD (legacy rows)."""
    s = str(value).strip()
    if not s:
        return None
    for fmt in _KNOWN_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_appt_date_series(series: pd.Series) -> pd.Series:
    """Parse a pandas Series of Appointment Date strings into datetime64,
    tolerating a mix of DD/MM/YYYY and legacy YYYY-MM-DD values."""
    return pd.to_datetime(series, format="mixed", dayfirst=True, errors="coerce")
