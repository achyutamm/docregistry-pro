"""
Small browser-side helpers for Streamlit widgets.
"""

import json

import streamlit.components.v1 as components


def nav_options(user_info: dict) -> list:
    """The sidebar menu, the same on every page that shows it."""
    nav = ["🏠 Dashboard", "📅 Calendar", "📝 New Entry", "🔍 Search Records", "✏️ Edit Records"]
    if user_info.get("role") == "admin":
        nav.append("👥 User Management")
    if user_info.get("config_access", False):
        nav.append("⚙️ Configuration")
    return nav


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
