"""
Small browser-side helpers for Streamlit widgets.
"""

import base64
import html
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_LOGIN_ART = Path(__file__).resolve().parent.parent / "assets" / "login_panel.svg"


def nav_options(user_info: dict) -> list:
    """The sidebar menu, the same on every page that shows it."""
    nav = ["🏠 Dashboard", "📅 Calendar", "📝 New Entry", "🔍 Search Records", "✏️ Edit Records", "🗑️ Delete Records"]
    if user_info.get("role") == "admin":
        nav.append("👥 User Management")
    if user_info.get("config_access", False):
        nav.append("⚙️ Configuration")
    return nav


def sidebar_theme():
    """Navy and gold left panel. Call on every page, before anything else goes in the sidebar."""
    st.sidebar.markdown(
        """<style>
[data-testid="stSidebar"] { background: linear-gradient(170deg, #17305A 0%, #0F2040 100%); }
[data-testid="stSidebar"] :is(h1, h2, h3, p, li, label, span) { color: #E8ECF4; }
[data-testid="stSidebar"] hr { border-color: rgba(212, 178, 92, .35); }
[data-testid="stSidebar"] button svg { color: #E6C777; fill: #E6C777; }

/* Menu */
[data-testid="stSidebar"] label[data-baseweb="radio"] { padding: .2rem 0; }
[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {
    background: transparent !important; border: 2px solid #8FA2C4; }
[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child > div { background: transparent !important; }
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) > div:first-child {
    background: #D4B25C !important; border-color: #D4B25C; }
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) > div:first-child > div {
    background: #0F2040 !important; }
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p { color: #E6C777; font-weight: 600; }

/* Buttons (Logout) */
[data-testid="stSidebar"] .stButton button { background: transparent; border: 1px solid #D4B25C; color: #E6C777; }
[data-testid="stSidebar"] .stButton button p { color: inherit; }
[data-testid="stSidebar"] .stButton button:hover { background: #D4B25C; border-color: #D4B25C; color: #0F2040; }
[data-testid="stSidebar"] .stButton button:disabled { opacity: .55; }

/* DEV banner */
[data-testid="stSidebar"] [data-testid="stAlert"] [role="alert"],
[data-testid="stSidebar"] [data-testid="stAlertContainer"] { background: rgba(212, 178, 92, .16); }
</style>""",
        unsafe_allow_html=True,
    )


def login_side_panel(company: str):
    """Navy panel with the illustration and the office name, in the sidebar of the login page."""
    try:
        art = base64.b64encode(_LOGIN_ART.read_bytes()).decode()
        img = f'<img src="data:image/svg+xml;base64,{art}" alt="" class="lp-art">'
    except OSError:
        img = ""     # the login page must still work without the picture
    points = "".join(f'<div class="lp-point"><span></span>{p}</div>'
                     for p in ("Appointments", "Document tracking", "WhatsApp reminders"))
    sidebar_theme()
    st.sidebar.markdown(
        """<style>
.lp { padding-top: 6vh; color: #F3F5F9; }
.lp-art { display: block; width: 100%; }
.lp-name { font-family: Georgia, 'Times New Roman', serif; font-size: 1.45rem; line-height: 1.25;
           font-weight: 600; margin: 1.6rem 0 .75rem; color: #FFFFFF; }
.lp-rule { width: 44px; height: 3px; background: #D4B25C; margin-bottom: .9rem; }
.lp-text { font-size: .95rem; line-height: 1.5; color: #C9D2E3; margin-bottom: 1.2rem; }
.lp-point { display: flex; align-items: center; gap: .6rem; font-size: .9rem; color: #E8ECF4; padding: .22rem 0; }
.lp-point span { width: 6px; height: 6px; transform: rotate(45deg); background: #D4B25C; flex: none; }
</style>"""
        f'<div class="lp">{img}<div class="lp-name">{html.escape(company)}</div><div class="lp-rule"></div>'
        '<div class="lp-text">Registry appointments, documents and reminders in one place.</div>'
        f'{points}</div>',
        unsafe_allow_html=True,
    )


def auto_number_textarea(label: str):
    """Live numbering for a st.text_area with this exact label (e.g. "Party 1 Partners"):
    focusing the empty box writes "1 ", and Enter starts the next line with "2 ", "3 "…

    Streamlit text areas can't react to typing, so this injects a tiny script into
    the page (via a 0-height component iframe, same origin). It listens on the
    parent document, so it keeps working after reruns re-create the text area.
    The saved value is still renumbered server-side (number_lines), so the list
    stays 1, 2, 3… even if a line is inserted or deleted in the middle.
    """
    components.html(
        """
<script>
(function () {
  const doc = window.parent.document;
  const LABEL = %s;
  const KEY = "__autoNumber_" + LABEL;
  if (window.parent[KEY]) return;          // install once per browser tab
  window.parent[KEY] = true;

  const setter = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, "value").set;
  let ownChange = false;                     // our own edits also fire "input" - don't react to them
  function setValue(el, value, caret) {
    ownChange = true;
    setter.call(el, value);                  // native setter so React/Streamlit sees the change
    el.dispatchEvent(new Event("input", { bubbles: true }));
    ownChange = false;
    el.setSelectionRange(caret, caret);
  }
  const isTarget = (el) => el && el.tagName === "TEXTAREA" && el.getAttribute("aria-label") === LABEL;

  doc.addEventListener("focusin", function (e) {
    const el = e.target;
    if (isTarget(el) && el.value === "") setValue(el, "1 ", 2);
  }, true);

  // Keep the "1 " on the first line while typing: deleting everything brings it back,
  // and typing over a selected-all box puts it in front of the new text.
  doc.addEventListener("input", function (e) {
    const el = e.target;
    if (ownChange || !isTarget(el) || doc.activeElement !== el) return;
    const v = el.value;
    if (/^\\d+ /.test(v)) return;
    // "", "1", "1Rakesh", " Rakesh", "Rakesh"... -> "1 " + the name
    const fixed = "1 " + v.replace(/^[\\s\\d.)]*/, "");
    setValue(el, fixed, Math.max(2, el.selectionStart + fixed.length - v.length));
  }, true);

  doc.addEventListener("keydown", function (e) {
    const el = e.target;
    if (!isTarget(el) || e.key !== "Enter" || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    const pos = el.selectionStart;
    const before = el.value.slice(0, pos), after = el.value.slice(el.selectionEnd);
    const next = before.split("\\n").length + 1;    // number for the new line
    const insert = "\\n" + next + " ";
    setValue(el, before + insert + after, pos + insert.length);
  }, true);
})();
</script>
"""
        % json.dumps(label),
        height=0,
    )
