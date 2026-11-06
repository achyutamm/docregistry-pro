"""
📝 New Entry - Data Entry Form
DocRegistry Pro - Phase 2
"""

import streamlit as st
from utils.sheets_cache import get_sheets_manager, clear_records_cache
from utils.date_utils import format_appt_date, appt_time_input
from utils.sheets_manager import number_lines, clean_lines
from utils.doc_fields import hidden_fields
from utils import gujarati_translit
from utils.ui_helpers import auto_number_textarea, nav_options, sidebar_theme
from utils import whatsapp_queue
from utils import phone_utils
from datetime import datetime, date, time
import pandas as pd
import yaml
from utils.app_env import CONFIG_FILE, IS_DEV

# ============================================
# PAGE CONFIG
# ============================================
st.set_page_config(
    page_title="New Entry - DocRegistry Pro",
    page_icon="📝",
    layout="wide"
)

# Hide Streamlit's auto-generated page navigation
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ============================================
# LOAD CONFIG
# ============================================
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

party_name_2_options = config.get("party_name_2_options", [])
sro_options          = config.get("sro_options", {})

# ============================================
# AUTHENTICATION CHECK
# ============================================
if not st.session_state.get('authenticated', False):
    st.warning("⚠️ Please login from the Home page first.")
    st.stop()

username  = st.session_state.get('username', 'Unknown')
user_info = st.session_state.get('user_info', {})

# ============================================
# CUSTOM SIDEBAR NAVIGATION
# ============================================
NAV_THIS_PAGE = "📝 New Entry"


def _on_nav_change():
    # Everything else in the menu lives in app.py. Put this menu back on New Entry
    # so it is right when staff come back to this page.
    st.session_state["nav_page"] = st.session_state["ne_sidebar_nav"]
    st.session_state["ne_sidebar_nav"] = NAV_THIS_PAGE
    st.session_state["_ne_leave_page"] = True


if st.session_state.pop("_ne_leave_page", False):
    st.switch_page("app.py")

sidebar_theme()
with st.sidebar:
    st.title("🏠 DocRegistry Pro")
    if IS_DEV:
        st.warning("🧪 **DEV environment** — dev Google Sheet and dev WhatsApp only. Nothing here reaches live data or real clients.")
    st.markdown(f"👋 **{user_info.get('name', username)}**")
    st.markdown(f"Role: **{user_info.get('role', '').title()}**")
    if "ne_sidebar_nav" not in st.session_state:
        st.session_state["ne_sidebar_nav"] = NAV_THIS_PAGE
    st.radio("Navigation", nav_options(user_info), label_visibility="collapsed",
             key="ne_sidebar_nav", on_change=_on_nav_change)
    if st.button("🚪 Logout", type="primary", use_container_width=True):
        st.session_state["_logout_requested"] = True
        st.switch_page("app.py")

# Send any WhatsApp messages queued while the service was down (throttled, never raises)
whatsapp_queue.auto_flush_if_due()

# ============================================
# PAGE HEADER
# ============================================
st.title("📝 New Registry Entry")
st.markdown("Add new registry records to the database")
st.divider()

top_col1, top_col2 = st.columns([1, 3])
with top_col1:
    st.info(f"👤 Logged in as: **{username}**")
with top_col2:
    st.caption("Your username will be automatically stored in the CREATED_BY column for accountability.")

# Saved-record pop-up label -> sheet column, to leave out fields this Document Type doesn't use
_PREVIEW_COLUMNS = {
    "Party 1 Partners": "Party_Name 1 Partners", "Party Name 2": "Party_Name 2",
    "GARVI App. No.": "Garvi_Application_ID", "Index App. No.": "Inedex_Application_No",
    "Index No.": "Index_No", "Search No.": "Search_No", "Title Status": "Title_Status", "Remark": "Remark",
}


@st.dialog("✅ Entry Saved", width="large")
def _saved_popup(saved):
    st.success(f"Saved in Tentative Records · Entry ID **{saved['entry_id']}**")
    st.caption(f"Created by {saved['created_by']} at {saved['timestamp']}")
    rec = saved["preview"][0]
    hidden = hidden_fields(config, rec.get("Document Type"))
    rows = [(k, "" if v is None else str(v)) for k, v in rec.items() if _PREVIEW_COLUMNS.get(k) not in hidden]
    st.dataframe(pd.DataFrame(rows, columns=["Field", "Value"]), hide_index=True,
                 use_container_width=True, height=36 * (len(rows) + 1))
    if st.button("OK", type="primary", use_container_width=True):
        st.rerun()


# The previous submission's result opens as a pop-up over the emptied form
if "_new_entry_saved" in st.session_state:
    _saved_popup(st.session_state.pop("_new_entry_saved"))

# ============================================
# FORM VERSION — bumping this clears all form fields reliably
# ============================================
if "ne_form_ver" not in st.session_state:
    st.session_state.ne_form_ver = 0
_fver = st.session_state.ne_form_ver

# Party Name 2 is a bank/branch dropdown for Mortgage & Release entries (the
# "party 2" there is always one of the configured NCB/bank branches); for every
# other document type it's a free-text field since party 2 is a person, not a
# fixed option.
BANK_PARTY2_DOC_TYPES = {"Mortgage", "Release"}

_FORM_KEYS = ["ne_district", "ne_sro", "doc_type", "entry_date", "entry_time_h", "entry_time_m", "entry_time_p",
              "party_name_1", "party1_cc", "party1_mobile", "party1_partners", "party_name_2_select",
              "party_name_2_text", "garvi_appli_no", "index_appli_no", "search_no", "index_no",
              "title_status", "remark"]


def _clear_form():
    st.session_state.ne_form_ver += 1
    for _k in _FORM_KEYS:
        st.session_state.pop(_k, None)

# ============================================
# DOCUMENT TYPE, DISTRICT & SRO — outside form so they react instantly
# ============================================

# Reset SRO whenever district changes
def _on_district_change():
    st.session_state["ne_sro"] = "-- Select SRO --"

st.markdown("### 📋 Entry Details")
c1, c2, c3 = st.columns(3)
with c1:
    doc_types = config.get("document_types", [])
    doc_type = st.selectbox("Document Type *", doc_types, key="doc_type")
with c2:
    district = st.selectbox(
        "District *",
        ["-- Select District --"] + list(sro_options.keys()),
        key="ne_district",
        on_change=_on_district_change
    )
with c3:
    current_district = st.session_state.get("ne_district", "-- Select District --")
    sro_list = sro_options.get(current_district, []) if current_district != "-- Select District --" else []
    if not sro_list:
        st.selectbox("SRO *", ["-- Select District First --"], key="ne_sro", disabled=True)
        sro = "-- Select SRO --"
    else:
        sro = st.selectbox(
            "SRO *",
            ["-- Select SRO --"] + sro_list,
            key="ne_sro"
        )

party2_is_bank = doc_type in BANK_PARTY2_DOC_TYPES
# Fields this Document Type doesn't use (Configuration -> Document Types) stay blank
_hidden = hidden_fields(config, doc_type)

# ============================================
# DATA ENTRY FORM
# ============================================
with st.form(f"registry_form_{_fver}", clear_on_submit=False):
    st.markdown("##### Appointment")
    st.caption("⏳ Every new entry starts as Tentative. No WhatsApp message goes out until the "
               "final date is confirmed in Edit Records.")

    # Row 1: Date & Time
    c1, c2 = st.columns(2)
    with c1:
        entry_date = st.date_input("Tentative Date *", value=date.today(), key="entry_date", format="DD/MM/YYYY")
    with c2:
        entry_time = appt_time_input("Tentative Time *", value=time(10, 0), key="entry_time")

    # Row 2: Party Information
    st.markdown("### 👥 Party Information")

    c1, c2 = st.columns(2)
    with c1:
        party_name_1 = st.text_input("Party Name 1 *", placeholder="Enter full party name", key="party_name_1")
    with c2:
        _cc_col, _mob_col = st.columns([1, 3])
        party1_cc = _cc_col.text_input("Code", value=phone_utils.DEFAULT_CODE, key="party1_cc", max_chars=4)
        party1_number = _mob_col.text_input(
            "Party 1 Mobile No", placeholder="e.g., 9876543210",
            key="party1_mobile", max_chars=10
        )
    # Stored form: plain 10 digits for +91, "+<code> <number>" otherwise
    party1_mobile = phone_utils.join(party1_cc, party1_number)

    party1_partners = st.text_area(
        "Party 1 Partners",
        placeholder="Click here and type the first partner name - press Enter for the next partner (1, 2, 3... are added automatically)",
        key="party1_partners", height=100,
    ) if "Party_Name 1 Partners" not in _hidden else ""

    if "Party_Name 2" in _hidden:
        party_name_2 = ""
    elif party2_is_bank:
        party_name_2 = st.selectbox(
            "Party Name 2",
            ["-- Select --"] + party_name_2_options,
            key="party_name_2_select"
        )
    else:
        party_name_2 = st.text_input(
            "Party Name 2", placeholder="Enter party name",
            key="party_name_2_text"
        ).strip()

    # Row 4: Application numbers, then Index no & Status - only the fields this type uses
    _row1 = [f for f in ("Garvi_Application_ID", "Inedex_Application_No", "Search_No") if f not in _hidden]
    _row2 = [f for f in ("Index_No", "Title_Status") if f not in _hidden]
    if _row1 or _row2:
        st.markdown("### 📂 Application Details")
    _cols = {**(dict(zip(_row1, st.columns(len(_row1)))) if _row1 else {}),
             **(dict(zip(_row2, st.columns(len(_row2)))) if _row2 else {})}
    garvi_appli_no = _cols["Garvi_Application_ID"].text_input(
        "GARVI Application No *", placeholder="ex. 20261100843645", key="garvi_appli_no"
    ) if "Garvi_Application_ID" in _cols else ""
    index_appli_no = _cols["Inedex_Application_No"].text_input(
        "Index Application No", placeholder="ex. 80120260372851", key="index_appli_no"
    ) if "Inedex_Application_No" in _cols else ""
    search_no = _cols["Search_No"].text_input(
        "Search No", placeholder="ex. 202612030719415", key="search_no"
    ) if "Search_No" in _cols else ""
    index_no = _cols["Index_No"].text_input(
        "Index No", placeholder="ex. 9729-2026", key="index_no"
    ) if "Index_No" in _cols else ""
    title_status = _cols["Title_Status"].selectbox(
        "Title Status *", ["Pending", "In Progress", "Completed", "Rejected"], index=0, key="title_status"
    ) if "Title_Status" in _cols else ""

    remark = st.text_area(
        "Remark", placeholder="Any additional notes or remarks...", key="remark", height=80
    ) if "Remark" not in _hidden else ""

    st.markdown("---")
    b1, b2, b3 = st.columns([2, 1, 1])
    with b1:
        submit_btn = st.form_submit_button("💾 Submit Entry", type="primary", use_container_width=True)
    with b2:
        preview_btn = st.form_submit_button("👁️ Preview", type="secondary", use_container_width=True)
    with b3:
        clear_btn = st.form_submit_button("🗑️ Clear Form", type="secondary", use_container_width=True)

# Live 1, 2, 3… numbering in the Party 1 Partners box while typing
auto_number_textarea("Party 1 Partners")

# ============================================
# FORM ACTIONS
# ============================================

def build_preview_df(entry_id, saved):
    _p1_saved, _partners_saved = saved
    return pd.DataFrame([{
        "Entry ID":          entry_id,
        "Document Type":     doc_type,
        "Appointment Date":  format_appt_date(entry_date),
        "Appointment Time":  str(entry_time),
        "Appt. Status":      "Tentative",
        "SRO":               sro,
        "Party Name 1":      _p1_saved,
        "Party 1 Mobile No": party1_mobile,
        "Party 1 Partners":  _partners_saved,
        "Party Name 2":      party_name_2 if party_name_2 != "-- Select --" else "",
        "GARVI App. No.":    garvi_appli_no,
        "Index App. No.":    index_appli_no,
        "Index No.":         index_no,
        "Search No.":        search_no,
        "Title Status":      title_status,
        "Remark":            remark,
        "Created By":        username,
    }])

if clear_btn:
    _clear_form()
    st.rerun()

_party2_value = party_name_2 if party_name_2 != "-- Select --" else ""
# Gujarati names get their English next to them: (label, as typed) for Party 1 and Partners
_xlit = gujarati_translit.settings()
_NAME_FIELDS = [
    ("Party Name 1",     party_name_1.strip()),
    ("Party 1 Partners", number_lines(party1_partners)),
]


def _auto_english():
    if not _xlit["enabled"]:
        return ("", "")
    return tuple(gujarati_translit.english_for(v) for _, v in _NAME_FIELDS)


def _saved_names(english):
    """What goes in the sheet for (Party 1, Partners): "Gujarati (English)" where there is English."""
    return tuple(gujarati_translit.with_english(v, en) if en else v
                 for (_, v), en in zip(_NAME_FIELDS, english))


# Same entry, same values: used to ignore a second click on Submit
def _entry_fingerprint():
    return (doc_type, format_appt_date(entry_date), str(entry_time), st.session_state.get("ne_sro"),
            party_name_1.strip(), party1_mobile.strip(), number_lines(party1_partners), _party2_value,
            garvi_appli_no.strip(), index_appli_no.strip(), index_no.strip(), search_no.strip(),
            title_status, remark.strip())


DOUBLE_SUBMIT_SECONDS = 120


def _matching_records():
    """Records already saved with the same key fields (config: duplicate_check)."""
    rules = config.get("duplicate_check") or {}
    if not rules.get("enabled", True):
        return []
    form = {
        "Doc_Type": doc_type, "Party_Name 1": party_name_1, "Appointment Date": format_appt_date(entry_date),
        "SRO": st.session_state.get("ne_sro", ""), "Party_Name 1 Mobile_No": party1_mobile,
        "Garvi_Application_ID": garvi_appli_no, "Inedex_Application_No": index_appli_no,
        "Index_No": index_no, "Search_No": search_no,
    }
    fields = rules.get("fields") or ["Doc_Type", "Party_Name 1", "Appointment Date", "SRO"]
    want = {f: form[f] for f in fields if f in form and str(form[f]).strip()}
    if not want:
        return []
    try:
        return get_sheets_manager().find_matching_records(want)
    except Exception:
        return []      # a failed check must not stop the office from saving


def _start_save():
    """After the duplicate check: staff check the English names first, or save now."""
    if _xlit["enabled"] and _xlit["review"] and any(_auto_english()):
        # Staff check the English spelling before saving (setting in Configuration)
        st.session_state["_ne_xlit_review"] = _auto_english()
    else:
        _save_entry(_auto_english())


if preview_btn and not submit_btn:
    st.info("👁️ Preview only – data is not saved to Google Sheets.")
    st.dataframe(build_preview_df("PREVIEW", _saved_names(_auto_english())),
                 hide_index=True, use_container_width=True)


def _validation_error():
    district = st.session_state.get("ne_district", "-- Select District --")
    _sro     = st.session_state.get("ne_sro", "-- Select SRO --")
    if not party_name_1.strip():
        return "Please enter Party Name 1."
    if district == "-- Select District --" or _sro == "-- Select SRO --":
        return "Please select a District and SRO."
    if not garvi_appli_no.strip():
        return "Please enter GARVI Application No."
    if phone_utils.validate(party1_cc, party1_number):
        return f"Party 1 Mobile No: {phone_utils.validate(party1_cc, party1_number)}"
    return None


def _save_entry(english):
    """english: (Party 1, Partners) in English - blank where the name is already English."""
    # A second click on Submit (or Save) for the same values is not saved again
    _fp = _entry_fingerprint()
    _last = st.session_state.get("_ne_last_save")
    if _last and _last["fp"] == _fp and (datetime.now() - _last["at"]).total_seconds() < DOUBLE_SUBMIT_SECONDS:
        st.info("✅ This entry is already saved" + (f" (Entry ID {_last['entry_id']})" if _last.get("entry_id") else "")
                + ". It was not saved a second time.")
        return
    st.session_state["_ne_last_save"] = {"fp": _fp, "at": datetime.now(), "entry_id": None}
    sro = st.session_state.get("ne_sro", "-- Select SRO --")
    _saved = _saved_names(english)
    _p1_saved, _partners_saved = _saved
    try:
        sheets_manager = get_sheets_manager()

        success, entry_id = sheets_manager.add_record(
            doc_type=doc_type,
            appointment_date=format_appt_date(entry_date),
            appointment_time=str(entry_time),
            sro=sro,
            party_name_1=_p1_saved,
            party1_mobile=party1_mobile.strip(),
            party_name_2=_party2_value,
            garvi_application_id=garvi_appli_no.strip(),
            index_application_no=index_appli_no.strip(),
            index_no=index_no.strip(),
            search_no=search_no.strip(),
            title_status=title_status,
            created_by=username,
            entry_date=str(date.today()),
            entry_time=datetime.now().strftime("%H:%M:%S"),
            remark=remark.strip(),
            party1_partners=_partners_saved,
        )

        if success:
            st.session_state["_ne_last_save"]["entry_id"] = entry_id
            clear_records_cache()
            st.toast(f"✅ Record saved! Entry ID: {entry_id}", icon="✅")
            st.session_state.pop("_ne_xlit_review", None)
            st.session_state["_new_entry_saved"] = {
                "entry_id":   entry_id,
                "created_by": username,
                "timestamp":  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "preview":    build_preview_df(entry_id, _saved).to_dict("records"),
            }
            _clear_form()
            st.rerun()
        else:
            st.session_state.pop("_ne_last_save", None)
            st.error("❌ Failed to save entry. Please try again.")
    except Exception as e:
        st.session_state.pop("_ne_last_save", None)
        st.error(f"❌ Error while saving to Google Sheets: {e}")


if submit_btn:
    _err = _validation_error()
    if _err:
        st.error(f"❌ {_err}")
    else:
        _dups = _matching_records()
        if _dups:
            st.session_state["_ne_dup"] = (_entry_fingerprint(), _dups)
        else:
            _start_save()

if "_ne_dup" in st.session_state:
    _dup_fp, _dups = st.session_state["_ne_dup"]
    if _dup_fp != _entry_fingerprint():
        st.session_state.pop("_ne_dup")       # the form was changed - check again on Submit
    else:
        with st.container(border=True):
            st.warning("⚠️ **This entry is already saved.** A record with the same Document Type, Party Name 1, "
                       "Date and SRO exists, so it was not added again.")
            st.dataframe(pd.DataFrame([{
                "Entry ID": str(r.get("Entry_ID", "")).replace(",", ""),
                "Status": r.get("Appointment_Status", ""),
                "Document Type": r.get("Doc_Type", ""),
                "Date": r.get("Appointment Date", ""),
                "SRO": r.get("SRO", ""),
                "Party Name 1": r.get("Party_Name 1", ""),
                "Created By": r.get("Created_By", ""),
                "Entry Date": f"{r.get('Entry_Date', '')} {r.get('Entry_Time', '')}".strip(),
            } for r in _dups]), hide_index=True, use_container_width=True)
            st.caption("If this really is a separate record (e.g. a second property for the same party), "
                       "press Save anyway.")
            dc1, dc2 = st.columns([3, 1])
            if dc1.button("💾 Save anyway as a new record", use_container_width=True):
                st.session_state.pop("_ne_dup")
                _start_save()
            if dc2.button("✖ Don't save", use_container_width=True):
                st.session_state.pop("_ne_dup")
                st.rerun()

if "_ne_xlit_review" in st.session_state:
    _suggested = st.session_state["_ne_xlit_review"]
    with st.container(border=True):
        st.markdown("#### 🔤 Check the English names")
        st.caption("These names are in Gujarati. They are saved with the English next to them, like "
                   "અવિનાશભાઈ પંચાલ (Avinashbhai Panchal). WhatsApp messages show the English. "
                   "Correct it if needed, then save.")
        _checked = []
        for n, ((label, guj), en) in enumerate(zip(_NAME_FIELDS, _suggested)):
            if not en:
                _checked.append("")
                continue
            st.markdown(f"**{label}:** " + guj.replace("\n", "  \n"))
            if "\n" in guj:
                _checked.append(st.text_area(f"{label} (English)", value=en, key=f"ne_xlit_{_fver}_{n}_{abs(hash(guj))}"))
            else:
                _checked.append(st.text_input(f"{label} (English)", value=en, key=f"ne_xlit_{_fver}_{n}_{abs(hash(guj))}"))
        rc1, rc2 = st.columns([3, 1])
        if rc1.button("💾 Save Entry with these English names", type="primary", use_container_width=True):
            _err = _validation_error()
            if _err:
                st.error(f"❌ {_err}")
            else:
                _p1c, _partnersc = _checked
                _partnersc = number_lines(_partnersc)
                if _partnersc and len(_partnersc.splitlines()) != len(_NAME_FIELDS[1][1].splitlines()):
                    st.error("❌ Party 1 Partners (English) needs one line for each partner.")
                else:
                    _save_entry((" ".join(_p1c.split()), _partnersc))
        if rc2.button("✖ Cancel", use_container_width=True):
            st.session_state.pop("_ne_xlit_review", None)
            st.rerun()

# ============================================
# HELP / INSTRUCTIONS
# ============================================
with st.expander("ℹ️ Form Instructions"):
    st.markdown("""
    ### How to fill this form

    **Required fields** (marked with `*`):
    - Document Type
    - Tentative Date & Time
    - SRO
    - Party Name 1
    - GARVI Application No
    - Title Status (when shown)

    **Optional fields** (the form shows the ones this Document Type uses):
    - Party 1 Mobile No
    - Party Name 2 (select from dropdown)
    - Index Application No
    - Index No
    - Search No

    **Notes:**
    - Each entry gets a unique `Entry ID` automatically.
    - `Created By` is filled with your username for accountability.
    - Use **Preview** to double-check data before submitting.
    """)

# ============================================
# FOOTER
# ============================================
_app_cfg  = config.get("app", {})
_company  = _app_cfg.get("company", "BK Mehta & Associates")
_app_name = _app_cfg.get("name", "DocRegistry Pro")
_version  = _app_cfg.get("version", "v1.0")
from datetime import datetime as _dt
_year = _dt.now().year
st.divider()
st.markdown(f"""
    <div style='text-align: center; padding: 10px; font-size: 12px; color: #888;'>
        🏛️ <strong>{_company}</strong> &nbsp;|&nbsp;
        {_app_name} {_version} &nbsp;|&nbsp;
        👨‍💻 Developed by <strong>Achyutam Mehta</strong> &nbsp;|&nbsp;
        &copy; {_year} All Rights Reserved
    </div>
""", unsafe_allow_html=True)
