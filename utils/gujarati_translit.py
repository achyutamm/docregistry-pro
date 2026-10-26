"""
Gujarati names -> English spelling (transliteration, not translation).

Our own rule-based converter, no external service or library: each Gujarati
letter maps to English letters, then the silent "a" Gujarati doesn't pronounce
is dropped (ગણપતલાલ -> Ganpatlal, not Ganapatalala). Words with a fixed
English spelling (મહેતા -> Mehta, મે. -> M/s) come from SPELLINGS plus the
admin's own list in Configuration (transliteration.corrections).

The Gujarati name stays in its column as typed; the English version goes in
the matching "(English)" column and is what WhatsApp messages use.
"""

import re

from utils.app_env import CONFIG_FILE

# Sheet column -> its English column
ENGLISH_COLUMNS = {
    "Party_Name 1":          "Party_Name 1 (English)",
    "Party_Name 1 Partners": "Party_Name 1 Partners (English)",
    "Party_Name 2":          "Party_Name 2 (English)",
}

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


def english_for(text) -> str:
    """Value for an "(English)" column: the English spelling when the name is in Gujarati, else blank."""
    return to_english(text) if has_gujarati(text) else ""


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
    """Copy of a sheet-style record with each party name replaced by its English
    version when one is saved - what WhatsApp messages should show."""
    rec = dict(record)
    for col, en_col in ENGLISH_COLUMNS.items():
        en = str(rec.get(en_col, "") or "").strip()
        if en and en.lower() not in ("nan", "none"):
            rec[col] = en
    return rec
