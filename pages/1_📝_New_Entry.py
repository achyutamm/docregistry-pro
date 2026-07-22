"""
📝 New Entry - Data Entry Form
DocRegistry Pro - Phase 2
"""

import streamlit as st
from utils.sheets_cache import get_sheets_manager, clear_records_cache
from utils.notification_router import notify_new_entry
from datetime import datetime, date, time
import pandas as pd
import yaml

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
with open("config.yaml", "r") as f:
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

# ============================================
# FORM VERSION — bumping this clears all form fields reliably
# ============================================
if "ne_form_ver" not in st.session_state:
    st.session_state.ne_form_ver = 0
_fver = st.session_state.ne_form_ver

def _clear_form():
    st.session_state.ne_form_ver += 1
    st.session_state.pop("ne_district", None)
    st.session_state.pop("ne_sro", None)

# ============================================
# DISTRICT & SRO — outside form so they react instantly
# ============================================

# Reset SRO whenever district changes
def _on_district_change():
    st.session_state["ne_sro"] = "-- Select SRO --"

st.markdown("### 📋 Entry Details")
c1, c2 = st.columns(2)
with c1:
    district = st.selectbox(
        "District *",
        ["-- Select District --"] + list(sro_options.keys()),
        key="ne_district",
        on_change=_on_district_change
    )
with c2:
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

# ============================================
# DATA ENTRY FORM
# ============================================
with st.form(f"registry_form_{_fver}", clear_on_submit=False):
    st.markdown("##### Document Type & Appointment")

    # Row 1: Document Type & Date
    c1, c2 = st.columns(2)
    with c1:
        doc_types = config.get("document_types", [])
        doc_type = st.selectbox("Document Type *", doc_types, key="doc_type")
    with c2:
        entry_date = st.date_input("Date *", value=date.today(), key="entry_date")

    # Row 2: Time only (District/SRO moved outside)
    entry_time = st.time_input("Time *", value=time(10, 0), key="entry_time")

    # Row 3: Party Information
    st.markdown("### 👥 Party Information")

    c1, c2 = st.columns(2)
    with c1:
        party_name_1 = st.text_input("Party Name 1 *", placeholder="Enter full party name", key="party_name_1")
    with c2:
        party1_mobile = st.text_input(
            "Party 1 Mobile No", placeholder="e.g., 9876543210",
            key="party1_mobile", max_chars=10
        )

    party_name_2 = st.selectbox(
        "Party Name 2",
        ["-- Select --"] + party_name_2_options,
        key="party_name_2"
    )

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

# ============================================
# FORM ACTIONS
# ============================================

def build_preview_df(entry_id="PREVIEW"):
    return pd.DataFrame([{
        "Entry ID":          entry_id,
        "Document Type":     doc_type,
        "Appointment Date":  str(entry_date),
        "Appointment Time":  str(entry_time),
        "SRO":               sro,
        "Party Name 1":      party_name_1,
        "Party 1 Mobile No": party1_mobile,
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

if preview_btn and not submit_btn:
    st.info("👁️ Preview only – data is not saved to Google Sheets.")
    st.dataframe(build_preview_df(), hide_index=True, use_container_width=True)

if submit_btn:
    district = st.session_state.get("ne_district", "-- Select District --")
    sro      = st.session_state.get("ne_sro", "-- Select SRO --")
    if not party_name_1.strip():
        st.error("❌ Please enter Party Name 1.")
    elif district == "-- Select District --" or sro == "-- Select SRO --":
        st.error("❌ Please select a District and SRO.")
    elif party1_mobile.strip() and not (party1_mobile.strip().isdigit() and len(party1_mobile.strip()) == 10):
        st.error("❌ Party 1 Mobile No must be exactly 10 digits.")
    else:
        try:
            sheets_manager = get_sheets_manager()

            success, entry_id = sheets_manager.add_record(
                doc_type=doc_type,
                appointment_date=str(entry_date),
                appointment_time=str(entry_time),
                sro=sro,
                party_name_1=party_name_1.strip(),
                party1_mobile=party1_mobile.strip(),
                party_name_2=party_name_2 if party_name_2 != "-- Select --" else "",
                garvi_application_id=garvi_appli_no.strip(),
                index_application_no=index_appli_no.strip(),
                index_no=index_no.strip(),
                search_no=search_no.strip(),
                title_status=title_status,
                created_by=username,
                entry_date=str(date.today()),
                entry_time=datetime.now().strftime("%H:%M:%S"),
                remark=remark.strip()
            )

            if success:
                clear_records_cache()
                notify_new_entry({
                    "entry_id":             entry_id,
                    "doc_type":             doc_type,
                    "appointment_date":     str(entry_date),
                    "appointment_time":     str(entry_time),
                    "sro":                  sro,
                    "party_name_1":         party_name_1.strip(),
                    "party1_mobile":        party1_mobile.strip(),
                    "party_name_2":         party_name_2 if party_name_2 != "-- Select --" else "",
                    "garvi_application_id": garvi_appli_no.strip(),
                    "index_application_no": index_appli_no.strip(),
                    "index_no":             index_no.strip(),
                    "search_no":            search_no.strip(),
                    "title_status":         title_status,
                    "remark":               remark.strip(),
                    "created_by":           username,
                    "entry_date":           str(date.today()),
                    "entry_time":           datetime.now().strftime("%H:%M:%S"),
                })
                st.toast(f"✅ Record saved! Entry ID: {entry_id}", icon="✅")
                st.success("✅ Entry saved successfully!")
                st.markdown(f"**Entry ID:** `{entry_id}`")
                st.markdown(f"**Created by:** `{username}` at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                st.markdown("### 📄 Saved Record")
                st.dataframe(build_preview_df(entry_id), hide_index=True, use_container_width=True)
                _clear_form()
            else:
                st.error("❌ Failed to save entry. Please try again.")
        except Exception as e:
            st.error(f"❌ Error while saving to Google Sheets: {e}")

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
