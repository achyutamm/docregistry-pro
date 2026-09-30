"""
Shared helpers for the Appointment Date column.

The column is stored in Google Sheets as DD/MM/YYYY text. Older rows written
before this format change are still ISO (YYYY-MM-DD), so every parser here
accepts both.
"""

import pandas as pd
from datetime import date, datetime, time

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


# =====================================================
# Appointment Time
# =====================================================
# The old st.time_input was a 24-hour picker, so afternoon slots were often
# saved as e.g. 03:50:00 for 3:50 PM. Registry appointments only happen in
# office hours, so a stored 01:00–07:59 can only mean PM.
def office_hours_minutes(mins: int) -> int:
    """Minutes since midnight, with 01:00–07:59 read as PM."""
    return mins + 12 * 60 if 1 * 60 <= mins < 8 * 60 else mins


def appt_time_input(label: str, value: time, key: str) -> time:
    """Hour / minute / AM-PM picker for Appointment Time. Returns a 24-hour
    datetime.time, so str(result) is still HH:MM:SS for the sheet."""
    import streamlit as st  # local import keeps this module usable outside Streamlit

    mins = office_hours_minutes(value.hour * 60 + value.minute)
    h24, minute = divmod(mins, 60)
    minutes = sorted(set(range(0, 60, 5)) | {minute})

    st.markdown(f"<p style='font-size:14px;margin-bottom:0.25rem'>{label}</p>", unsafe_allow_html=True)
    c_h, c_m, c_p = st.columns(3)
    hour12 = c_h.selectbox("Hour", list(range(1, 13)), index=((h24 % 12) or 12) - 1,
                           key=f"{key}_h", label_visibility="collapsed")
    minute = c_m.selectbox("Minute", minutes, index=minutes.index(minute),
                           format_func=lambda m: f"{m:02d}",
                           key=f"{key}_m", label_visibility="collapsed")
    period = c_p.selectbox("AM/PM", ["AM", "PM"], index=0 if h24 < 12 else 1,
                           key=f"{key}_p", label_visibility="collapsed")
    return time(hour12 % 12 + (12 if period == "PM" else 0), minute)
