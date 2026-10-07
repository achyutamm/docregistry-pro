"""
Small browser-side helpers for Streamlit widgets.
"""

import json

import streamlit.components.v1 as components


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
  function setValue(el, value, caret) {
    setter.call(el, value);                  // native setter so React/Streamlit sees the change
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.setSelectionRange(caret, caret);
  }
  const isTarget = (el) => el && el.tagName === "TEXTAREA" && el.getAttribute("aria-label") === LABEL;

  doc.addEventListener("focusin", function (e) {
    const el = e.target;
    if (isTarget(el) && el.value === "") setValue(el, "1 ", 2);
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
