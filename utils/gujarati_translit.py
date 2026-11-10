"""
Gujarati names -> English spelling (transliteration, not translation).

Our own rule-based converter, no external service or library: each Gujarati
letter maps to English letters, then the silent "a" Gujarati doesn't pronounce
is dropped (ગણપતલાલ -> Ganpatlal, not Ganapatalala). Words with a fixed
English spelling (મહેતા -> Mehta, મે. -> M/s) come from SPELLINGS plus the
admin's own list in Configuration (transliteration.corrections).

Party Name 1 and Party 1 Partners keep both spellings in the same cell:
"અવિનાશભાઈ પંચાલ (Avinashbhai Panchal)", and for partners, line by line,
"1 રમેશ પટેલ (Ramesh Patel)". WhatsApp messages show only the English.
"""

import re

from utils.app_env import CONFIG_FILE

# Sheet columns that can hold "Gujarati (English)"
NAME_COLUMNS = ("Party_Name 1", "Party_Name 1 Partners")

_CONS = {
    "ક": "k", "ખ": "kh", "ગ": "g", "ઘ": "gh", "ઙ": "n", "ચ": "ch", "છ": "chh", "જ": "j", "ઝ": "jh",
    "ઞ": "n", "ટ": "t", "ઠ": "th", "ડ": "d", "ઢ": "dh", "ણ": "n", "ત": "t", "થ": "th", "દ": "d",
    "ધ": "dh", "ન": "n", "પ": "p", "ફ": "f", "બ": "b", "ભ": "bh", "મ": "m", "ય": "y", "ર": "r",
    "લ": "l", "ળ": "l", "વ": "v", "શ": "sh", "ષ": "sh", "સ": "s", "હ": "h",
}
_SINGLE = set(_CONS.values())   # one consonant (bh, chh...), as opposed to a joined cluster
_VOWELS = {"અ": "a", "આ": "a", "ઇ": "i", "ઈ": "i", "ઉ": "u", "ઊ": "u", "ઋ": "ru", "એ": "e",
           "ઐ": "ai", "ઓ": "o", "ઔ": "au", "ઍ": "e", "ઑ": "o"}
_MATRAS = {"ા": "a", "િ": "i", "ી": "i", "ુ": "u", "ૂ": "u", "ૃ": "ru", "ે": "e", "ૈ": "ai",
           "ો": "o", "ૌ": "au", "ૅ": "e", "ૉ": "o"}
_VIRAMA, _NUKTA = "્", "઼"
_NASAL = ("ં", "ઁ")
_VISARGA = "ઃ"
_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")
# A word ending in a joined cluster like dr / tr / shn / ty keeps its "a": Chandra, Krushna, Satya
_KEEP_FINAL_A_AFTER = {"r", "y", "v", "n"}

# Words with a fixed English spelling (admins add more in Configuration)
SPELLINGS = {
    "મે.": "M/s", "મેસર્સ": "M/s", "શ્રી": "Shri", "ધી": "The", "પ્રા.": "Pvt.", "લિ.": "Ltd.",
    "પ્રાઇવેટ": "Private", "પ્રાયવેટ": "Private", "લિમિટેડ": "Limited", "ટ્રસ્ટ": "Trust",
    "બેંક": "Bank", "બેન્ક": "Bank", "કો-ઓપ.": "Co-op.", "કો.ઓપ.": "Co-op.", "એલએલપી": "LLP",
    "મહેતા": "Mehta",
}

_GUJ = re.compile(r"[઀-૿]")
_NUMBERED = re.compile(r"^(\d+\s+)(.*)$")          # "1 Name"
_PAIR = re.compile(r"^(.*\S)\s*\(([^()]*)\)$")     # "Name (English)"


def has_gujarati(text) -> bool:
    return bool(_GUJ.search(str(text or "")))


def _syllables(word):
    """Split into syllables: consonant cluster + vowel; inh=True when the vowel is the unwritten 'a'."""
    out, i, n = [], 0, len(word)
    while i < n:
        ch = word[i]
        if ch in _VOWELS:
            out.append({"c": "", "v": _VOWELS[ch], "nas": "", "inh": False})
            i += 1
        elif ch in _CONS:
            cl = _CONS[ch]
            i += 1
            if i < n and word[i] == _NUKTA:
                i += 1
            while i + 1 < n and word[i] == _VIRAMA and word[i + 1] in _CONS:
                cl += _CONS[word[i + 1]]
                i += 2
                if i < n and word[i] == _NUKTA:
                    i += 1
            if i < n and word[i] == _VIRAMA:          # consonant with no vowel
                out.append({"c": cl, "v": "", "nas": "", "inh": False})
                i += 1
            elif i < n and word[i] in _MATRAS:
                out.append({"c": cl, "v": _MATRAS[word[i]], "nas": "", "inh": False})
                i += 1
            else:
                out.append({"c": cl, "v": "a", "nas": "", "inh": True})
        elif ch in _NASAL and out:
            out[-1]["nas"] = "n"
            i += 1
        elif ch == _VISARGA and out:
            out[-1]["nas"] += "h"
            i += 1
        else:
            out.append({"c": "", "v": ch.translate(_DIGITS), "nas": "", "inh": False})
            i += 1
    return out


def _word(word: str) -> str:
    s = _syllables(word)
    if not s:
        return word
    # Word-final silent "a": Patel, Ganpatlal - but Chandra, Krushna keep it
    last = s[-1]
    if last["inh"] and not last["nas"] and len(s) > 1:
        if last["c"] in _SINGLE or last["c"][-1:] not in _KEEP_FINAL_A_AFTER:
            last["v"] = ""
    # Medial silent "a", right to left: vowel + C[a] + C + vowel -> drop it (Ganpat, Rameshchandra)
    for k in range(len(s) - 2, 0, -1):
        cur, prev, nxt = s[k], s[k - 1], s[k + 1]
        if (cur["inh"] and not cur["nas"] and cur["v"] == "a" and cur["c"] in _SINGLE
                and prev["v"] and nxt["c"] in _SINGLE and nxt["v"]):
            cur["v"] = ""
    text = ""
    for k, x in enumerate(s):
        nas = x["nas"]
        if nas.startswith("n") and k + 1 < len(s) and s[k + 1]["c"][:1] in ("p", "b", "m"):
            nas = "m" + nas[1:]       # અંબાલાલ -> Ambalal
        text += x["c"] + x["v"] + nas
    return text


def _config_spellings() -> dict:
    try:
        import yaml
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        rows = (cfg.get("transliteration") or {}).get("corrections") or []
        return {str(r.get("gujarati", "")).strip(): str(r.get("english", "")).strip()
                for r in rows if str(r.get("gujarati", "")).strip() and str(r.get("english", "")).strip()}
    except Exception:
        return {}


def to_english(text, spellings: dict = None) -> str:
    """Gujarati words -> English; English words, digits, numbering and punctuation are kept.
    Text without Gujarati comes back unchanged."""
    text = str(text or "")
    if not has_gujarati(text):
        return text
    words = {**SPELLINGS, **(spellings if spellings is not None else _config_spellings())}
    out = []
    for tok in re.split(r"(\s+)", text):
        if not has_gujarati(tok):
            out.append(tok)
            continue
        # Keep trailing punctuation like "," outside the lookup, unless the word itself has it (મે.)
        key, trail = (tok, "") if tok in words else (tok.rstrip(",;:"), tok[len(tok.rstrip(",;:")):])
        if key in words:
            out.append(words[key] + trail)
        else:
            w = _word(key)
            out.append(w[:1].upper() + w[1:] + trail)
    return "".join(out)


def _split_line(line):
    """"1 રમેશ પટેલ (Ramesh Patel)" -> ("1 ", "રમેશ પટેલ", "Ramesh Patel"); English is "" if there is none."""
    line = str(line or "").strip()
    m = _NUMBERED.match(line)
    num, body = (m.group(1), m.group(2)) if m else ("", line)
    p = _PAIR.match(body)
    if p and has_gujarati(p.group(1)) and p.group(2).strip() and not has_gujarati(p.group(2)):
        return num, p.group(1), p.group(2).strip()
    return num, body, ""


def english_only(text) -> str:
    """The English side of each "Gujarati (English)" line, keeping the numbering.
    Lines without a saved English spelling come back as they are."""
    parts = (_split_line(line) for line in str(text or "").splitlines())
    return "\n".join(f"{num}{en or body}" for num, body, en in parts)


def english_for(text) -> str:
    """English spelling when the text has Gujarati, else blank (= nothing to convert)."""
    return to_english(english_only(text)) if has_gujarati(text) else ""


def with_english(text, english=None) -> str:
    """Gujarati lines -> "Gujarati (English)", line by line, keeping the numbering; other lines
    are unchanged. english: the spelling to use, with the same lines as text. Without it, a line
    that already has its English keeps it (so a correction survives) and the rest are converted."""
    typed = None if english is None else str(english).splitlines()
    out = []
    for i, line in enumerate(str(text or "").splitlines()):
        num, body, en = _split_line(line)
        if has_gujarati(body):
            if typed is not None:
                en = _split_line(typed[i])[1] if i < len(typed) else ""
            elif not en:
                en = to_english(body)
        out.append(f"{num}{body} ({en})" if en else f"{num}{body}")
    return "\n".join(out)


def settings() -> dict:
    """transliteration settings from config: enabled (default on) and review (staff check, default on)."""
    try:
        import yaml
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            t = (yaml.safe_load(f) or {}).get("transliteration") or {}
    except Exception:
        t = {}
    return {"enabled": bool(t.get("enabled", True)), "review": bool(t.get("review_before_save", True))}


def use_english_names(record: dict) -> dict:
    """Copy of a sheet-style record with the names in English only - what WhatsApp messages show."""
    rec = dict(record)
    for col in NAME_COLUMNS:
        if col in rec:
            rec[col] = english_only(rec[col])
    return rec


def use_english_changes(changes) -> list:
    """Edit changes (field, old, new) for WhatsApp: names in English only. A name whose
    English didn't change (only the Gujarati side was edited) is left out."""
    out = []
    for field, old, new in changes:
        if field in NAME_COLUMNS:
            old, new = english_only(old), english_only(new)
            if old == new:
                continue
        out.append((field, old, new))
    return out
