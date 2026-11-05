"""
📝 New Entry - Data Entry Form
DocRegistry Pro - Phase 2
"""

import streamlit as st
from utils.sheets_cache import get_sheets_manager, clear_records_cache
from utils.notification_router import notify_new_entry, send_party1_checklist
from utils.date_utils import format_appt_date, appt_time_input
from utils.sheets_manager import number_lines, clean_lines
from utils import gujarati_translit
from utils.ui_helpers import auto_number_textarea
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
with st.sidebar:
    st.title("🏛️ DocRegistry Pro")
    if IS_DEV:
        st.warning("🧪 **DEV environment** — dev Google Sheet and dev WhatsApp only. Nothing here reaches live data or real clients.")
    st.markdown(f"👋 **{user_info.get('name', username)}**")
    st.markdown(f"Role: **{user_info.get('role', '').title()}**")
    st.divider()
    if st.button("🏠 Dashboard",       use_container_width=True):
        st.switch_page("app.py")
    st.button("📝 New Entry", use_container_width=True, disabled=True, type="primary")
    if st.button("🔍 Search Records",  use_container_width=True):
        st.switch_page("pages/2_Search_Records.py")
    if st.button("✏️ Edit Records",    use_container_width=True):
        st.session_state["nav_page"] = "✏️ Edit Records"
        st.switch_page("app.py")
    st.divider()
    if st.button("🚪 Logout", type="primary", use_container_width=True):
        for _k in list(st.session_state.keys()):
            del st.session_state[_k]
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

# Show the previous submission's result (if any) up here — set right before the
# form-clearing rerun below, so it survives the reset instead of vanishing with
# the emptied fields.
if "_new_entry_saved" in st.session_state:
    _saved = st.session_state.pop("_new_entry_saved")
    st.success("✅ Entry saved successfully!")
    st.markdown(f"**Entry ID:** `{_saved['entry_id']}`")
    st.markdown(f"**Created by:** `{_saved['created_by']}` at {_saved['timestamp']}")
    _wa_state, _wa_detail = _saved.get("party1_wa", ("skipped", ""))
    if _wa_state == "sent":
        st.success(f"📱 {_wa_detail}")
    elif _wa_state == "queued":
        st.warning(f"📥 {_wa_detail}")
    elif _wa_state == "not_on_whatsapp":
        st.error(f"⚠️ {_wa_detail}")
    elif _wa_state == "failed":
        st.warning(f"⚠️ {_wa_detail}")
    elif _wa_state == "tentative":
        st.info(f"⏳ {_wa_detail}")
    elif _wa_detail:
        st.info(f"📱 WhatsApp to Party 1 not sent: {_wa_detail}")
    st.markdown("### 📄 Saved Record")
    st.dataframe(pd.DataFrame(_saved["preview"]), hide_index=True, use_container_width=True)
    st.divider()

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

def _clear_form():
    st.session_state.ne_form_ver += 1
    st.session_state.pop("ne_district", None)
    st.session_state.pop("ne_sro", None)
    st.session_state.pop("doc_type", None)

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

# ============================================
# DATA ENTRY FORM
# ============================================
with st.form(f"registry_form_{_fver}", clear_on_submit=False):
    st.markdown("##### Appointment")

    # Row 1: Date & Time
    c1, c2 = st.columns(2)
    with c1:
        entry_date = st.date_input("Date *", value=date.today(), key="entry_date", format="DD/MM/YYYY")
    with c2:
        entry_time = appt_time_input("Time *", value=time(10, 0), key="entry_time")
    appt_tentative = st.checkbox(
        "⏳ Date not final yet (tentative / placeholder)", key="appt_tentative",
        help="Saves the entry with this date as a placeholder. The Party 1 checklist and daily "
             "reminders wait until you change the status to Confirmed in Edit Records.",
    )
    appointment_status = "Tentative" if appt_tentative else "Confirmed"

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
    )

    if party2_is_bank:
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

    # Row 4: Application numbers
    st.markdown("### 📂 Application Details")
    c1, c2, c3 = st.columns(3)
    with c1:
        garvi_appli_no = st.text_input("GARVI Application No", placeholder="ex. 20261100843645", key="garvi_appli_no")
    with c2:
        index_appli_no = st.text_input("Index Application No", placeholder="ex. 80120260372851", key="index_appli_no")
    with c3:
        search_no = st.text_input("Search No", placeholder="ex. 202612030719415", key="search_no")

    # Row 5: Index no & Status
    c1, c2 = st.columns(2)
    with c1:
        index_no = st.text_input("Index No", placeholder="ex. 9729-2026", key="index_no")
    with c2:
        status_options = ["Pending", "In Progress", "Completed", "Rejected"]
        title_status = st.selectbox("Title Status *", status_options, index=0, key="title_status")

    remark = st.text_area("Remark", placeholder="Any additional notes or remarks...", key="remark", height=80)

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
        "Appt. Status":      appointment_status,
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
    if phone_utils.validate(party1_cc, party1_number):
        return f"Party 1 Mobile No: {phone_utils.validate(party1_cc, party1_number)}"
    return None


def _save_entry(english):
    """english: (Party 1, Partners) in English - blank where the name is already English."""
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
            appointment_status=appointment_status,
        )

        if success:
            clear_records_cache()
            # Messages use the English names
            _record = {
                "entry_id":             entry_id,
                "doc_type":             doc_type,
                "appointment_date":     format_appt_date(entry_date),
                "appointment_time":     str(entry_time),
                "sro":                  sro,
                "party_name_1":         gujarati_translit.english_only(_p1_saved),
                "party1_mobile":        party1_mobile.strip(),
                "party1_partners":      gujarati_translit.english_only(_partners_saved),
                "party_name_2":         _party2_value,
                "garvi_application_id": garvi_appli_no.strip(),
                "index_application_no": index_appli_no.strip(),
                "index_no":             index_no.strip(),
                "search_no":            search_no.strip(),
                "title_status":         title_status,
                "remark":               remark.strip(),
                "created_by":           username,
                "entry_date":           str(date.today()),
                "entry_time":           datetime.now().strftime("%H:%M:%S"),
                "appointment_status":   appointment_status,
            }
            if appt_tentative:
                # The date is a placeholder - the checklist goes out on confirmation
                _wa_status = ("tentative", "Tentative appointment - the Party 1 checklist will be "
                                           "sent when you mark it Confirmed in Edit Records.")
            else:
                with st.spinner("📱 Sending WhatsApp checklist to Party 1..."):
                    _wa_status = send_party1_checklist(_record)

            # WhatsApp worked, so the service is up: send anything left pending
            if _wa_status[0] == "sent":
                try:
                    whatsapp_queue.flush()
                except Exception:
                    pass

            notify_new_entry(_record)
            st.toast(f"✅ Record saved! Entry ID: {entry_id}", icon="✅")
            st.session_state.pop("_ne_xlit_review", None)
            st.session_state["_new_entry_saved"] = {
                "entry_id":   entry_id,
                "created_by": username,
                "timestamp":  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "preview":    build_preview_df(entry_id, _saved).to_dict("records"),
                "party1_wa":  _wa_status,
            }
            _clear_form()
            st.rerun()
        else:
            st.error("❌ Failed to save entry. Please try again.")
    except Exception as e:
        st.error(f"❌ Error while saving to Google Sheets: {e}")


if submit_btn:
    _err = _validation_error()
    if _err:
        st.error(f"❌ {_err}")
    elif _xlit["enabled"] and _xlit["review"] and any(_auto_english()):
        # Staff check the English spelling before saving (setting in Configuration)
        st.session_state["_ne_xlit_review"] = _auto_english()
    else:
        _save_entry(_auto_english())

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
    - Date & Time
    - SRO
    - Party Name 1
    - Title Status

    **Optional fields**:
    - Party 1 Mobile No
    - Party Name 2 (select from dropdown)
    - GARVI Application No
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
