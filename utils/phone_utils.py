"""
Country code + mobile number helpers.

Storage rule for the Party 1 Mobile No column (and the checklist test number):
  * India (+91) is stored as the plain 10-digit number, exactly as before,
    so existing rows and every message that prints the number are unchanged.
  * Any other country code is stored as "+<code> <number>", e.g. "+1 4155551234".
"""

import re

DEFAULT_CODE = "+91"


def clean_code(code) -> str:
    """'91', ' +91 ' -> '+91'; empty -> the default (+91)."""
    digits = "".join(ch for ch in str(code or "") if ch.isdigit())
    return f"+{digits}" if digits else DEFAULT_CODE


def validate(code, number) -> str:
    """Return an error message, or "" when the code + number are valid.
    An empty number is valid (the field is optional)."""
    number = str(number or "").strip()
    if not number:
        return ""
    if not re.fullmatch(r"\+?\d{1,3}", str(code or "").strip() or DEFAULT_CODE):
        return "Country code must be like +91 (1–3 digits)."
    if not number.isdigit():
        return "Mobile number must contain digits only."
    if clean_code(code) == DEFAULT_CODE:
        if len(number) != 10:
            return "Mobile number must be exactly 10 digits for +91."
    elif not 6 <= len(number) <= 10:
        return "Mobile number must be 6–10 digits."
    return ""


def join(code, number) -> str:
    """Value to store: plain number for +91, '+<code> <number>' otherwise."""
    number = str(number or "").strip()
    if not number:
        return ""
    code = clean_code(code)
    return number if code == DEFAULT_CODE else f"{code} {number}"


def split(stored) -> tuple:
    """Stored value -> (country code, number). Plain numbers are +91."""
    s = str(stored or "").strip()
    m = re.fullmatch(r"\+(\d{1,3})\s+(\d+)", s)
    if m:
        return f"+{m.group(1)}", m.group(2)
    return DEFAULT_CODE, s
