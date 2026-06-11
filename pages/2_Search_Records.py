"""
🔍 Search Records - DocRegistry Pro
"""

import streamlit as st
from utils.sheets_manager import SheetsManager
import pandas as pd
import yaml

# ============================================
# PAGE CONFIG
# ============================================
st.set_page_config(
    page_title="Search Records - DocRegistry Pro",
    page_icon="🔍",
    layout="wide"
)

# Hide Streamlit's auto-generated page navigation
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ============================================
# AUTH CHECK
# ============================================
if not st.session_state.get('authenticated', False):
    st.warning("⚠️ Please login from the Home page first.")
    st.stop()

username  = st.session_state.get('username', 'Unknown')
user_info = st.session_state.get('user_info', {})

# ============================================
# LOAD CONFIG
# ============================================
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

DOCUMENT_TYPES       = config.get("document_types", [])
PARTY_NAME_2_OPTIONS = config.get("party_name_2_options", [])
SRO_CONFIG           = config.get("sro_options", {})
SRO_ALL_FLAT         = [sro for sros in SRO_CONFIG.values() for sro in sros]
STATUS_OPTIONS       = ["Pending", "In Progress", "Completed", "Rejected"]

# ============================================
# COLUMN DISPLAY MAPPING
# ============================================
COL_DISPLAY = {
    "Entry_ID":               "Entry ID",
    "Doc_Type":               "Document Type",
    "Appointment Date":       "Appointment Date",
    "Appointment Time":       "Appointment Time",
    "SRO":                    "SRO",
    "Party_Name 1":           "Party Name 1",
    "Party_Name 1 Mobile_No": "Party 1 Mobile No",
    "Party_Name 2":           "Party Name 2",
    "Garvi_Application_ID":   "GARVI Application No",
    "Inedex_Application_No":  "Index Application No",
    "Index_No":               "Index No",
    "Search_No":              "Search No",
    "Title_Status":           "Title Status",
    "Created_By":             "Created By",
    "Entry_Date":             "Entry Date",
    "Entry_Time":             "Entry Time",
}

FIELD_LABELS = {
    "Doc_Type":               "Document Type",
    "Appointment Date":       "Appointment Date",
    "Appointment Time":       "Appointment Time",
    "SRO":                    "SRO",
    "Party_Name 1":           "Party Name 1",
    "Party_Name 1 Mobile_No": "Party 1 Mobile No",
    "Party_Name 2":           "Party Name 2",
    "Garvi_Application_ID":   "GARVI App. No.",
    "Inedex_Application_No":  "Index App. No.",
    "Index_No":               "Index No.",
    "Search_No":              "Search No.",
    "Title_Status":           "Title Status",
}

def display_df(df):
    return df.rename(columns=COL_DISPLAY)

# ============================================
# CUSTOM SIDEBAR NAVIGATION
# ============================================
with st.sidebar:
    st.title("🏛️ DocRegistry Pro")
    st.markdown(f"👋 **{user_info.get('name', username)}**")
    st.markdown(f"Role: **{user_info.get('role', '').title()}**")
    st.divider()
    if st.button("🏠 Dashboard",      use_container_width=True):
        st.switch_page("app.py")
    if st.button("📝 New Entry",       use_container_width=True):
        st.switch_page("pages/1_📝_New_Entry.py")
    st.button("🔍 Search Records", use_container_width=True, disabled=True, type="primary")
    if st.button("✏️ Edit Records",   use_container_width=True):
        st.switch_page("app.py")
    st.divider()
    if st.button("🚪 Logout", type="primary", use_container_width=True):
        for _k in list(st.session_state.keys()):
            del st.session_state[_k]
        st.switch_page("app.py")

# ============================================
# LOAD DATA
# ============================================
try:
    sheets_manager = SheetsManager()
    df = sheets_manager.get_all_records()
except Exception as e:
    st.error(f"❌ Failed to load records: {e}")
    st.stop()

# ============================================
# PAGE HEADER
# ============================================
st.title("🔍 Search Records")
st.markdown("Search and filter registry entries from the database")
st.divider()

if df.empty:
    st.info("No records found in the database.")
    st.stop()

# ============================================
# SEARCH & FILTER PANEL (counter-key for clear)
# ============================================
if "search_filter_key" not in st.session_state:
    st.session_state["search_filter_key"] = 0
fk = st.session_state["search_filter_key"]

with st.expander("🔎 Search & Filters", expanded=True):
    col1, col2, col_search, col_clear = st.columns([3, 3, 1, 1])
    with col1:
        keyword = st.text_input(
            "Search by Party Name / Entry ID / GARVI No / Index No",
            placeholder="Type to search...",
            key=f"search_keyword_{fk}"
        )
    with col2:
        status_filter = st.multiselect(
            "Title Status", options=STATUS_OPTIONS, default=[], key=f"status_filter_{fk}"
        )
    with col_search:
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("🔍 Search", use_container_width=True, key="search_btn")
    with col_clear:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Clear Filters", use_container_width=True, key="clear_filters_btn"):
            st.session_state["search_filter_key"] += 1
            st.rerun()

    col3, col4, col5 = st.columns(3)
    with col3:
        doc_type_filter = st.multiselect(
            "Document Type", options=DOCUMENT_TYPES, default=[], key=f"doc_type_filter_{fk}"
        )
    with col4:
        sro_filter = st.multiselect(
            "SRO", options=sorted(SRO_ALL_FLAT), default=[], key=f"sro_filter_{fk}"
        )
    with col5:
        party2_filter = st.multiselect(
            "Party Name 2", options=PARTY_NAME_2_OPTIONS, default=[], key=f"party2_filter_{fk}"
        )

    col6, col7 = st.columns(2)
    with col6:
        date_from = st.date_input("Appointment Date From", value=None, key=f"date_from_{fk}")
    with col7:
        date_to = st.date_input("Appointment Date To", value=None, key=f"date_to_{fk}")

# ============================================
# APPLY FILTERS
# ============================================
filtered = df.copy()

if keyword.strip():
    kw   = keyword.strip().lower()
    mask = (
        filtered["Party_Name 1"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered["Entry_ID"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered["Garvi_Application_ID"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered["Index_No"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered["Inedex_Application_No"].astype(str).str.lower().str.contains(kw, na=False) |
        filtered["Search_No"].astype(str).str.lower().str.contains(kw, na=False)
    )
    filtered = filtered[mask]

if status_filter:
    filtered = filtered[filtered["Title_Status"].isin(status_filter)]
if doc_type_filter:
    filtered = filtered[filtered["Doc_Type"].isin(doc_type_filter)]
if sro_filter:
    filtered = filtered[filtered["SRO"].isin(sro_filter)]
if party2_filter:
    filtered = filtered[filtered["Party_Name 2"].isin(party2_filter)]
if date_from:
    filtered = filtered[filtered["Appointment Date"] >= str(date_from)]
if date_to:
    filtered = filtered[filtered["Appointment Date"] <= str(date_to)]

# ============================================
# SUMMARY METRICS
# ============================================
st.divider()
col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Total Results", len(filtered))
col_b.metric("Pending",     len(filtered[filtered["Title_Status"].str.lower() == "pending"])     if not filtered.empty else 0)
col_c.metric("In Progress", len(filtered[filtered["Title_Status"].str.lower() == "in progress"]) if not filtered.empty else 0)
col_d.metric("Completed",   len(filtered[filtered["Title_Status"].str.lower() == "completed"])   if not filtered.empty else 0)

st.divider()

# ============================================
# RESULTS TABLE
# ============================================
col_title, col_dl = st.columns([4, 1])
with col_title:
    st.subheader(f"📄 Results ({len(filtered)} records)")
with col_dl:
    st.download_button(
        "⬇️ Download CSV",
        data=filtered.to_csv(index=False),
        file_name="search_results.csv",
        mime="text/csv",
        use_container_width=True
    )

if filtered.empty:
    st.info("No records match your search criteria.")
else:
    display_cols = [
        "Entry_ID", "Doc_Type", "Appointment Date", "Appointment Time",
        "SRO", "Party_Name 1", "Party_Name 1 Mobile_No", "Party_Name 2",
        "Garvi_Application_ID", "Inedex_Application_No", "Index_No",
        "Search_No", "Title_Status", "Created_By", "Entry_Date", "Entry_Time"
    ]
    display_cols = [c for c in display_cols if c in filtered.columns]
    result_df = filtered[display_cols].reset_index(drop=True)

    st.caption("👆 Click any row to view its edit history below.")
    table_event = st.dataframe(
        display_df(result_df),
        use_container_width=True,
        height=400,
        on_select="rerun",
        selection_mode="single-row"
    )

    # ── Record History on row click ─────────────────────────────
    selected_rows = table_event.selection.rows
    if selected_rows:
        sel_idx = selected_rows[0]
        sel_rec = result_df.iloc[sel_idx]
        selected_entry_id = str(sel_rec.get("Entry_ID", "")).replace(",", "")

        st.divider()
        st.subheader(
            f"🕓 Edit History — "
            f"{sel_rec.get('Party_Name 1', '')} | "
            f"{sel_rec.get('Doc_Type', '')} | "
            f"{sel_rec.get('Appointment Date', '')}"
        )

        try:
            h_df = sheets_manager.get_history(selected_entry_id)
            edit_rows = []
            if not h_df.empty:
                h_df["Entry_ID"] = h_df["Entry_ID"].astype(str).str.replace(",", "", regex=False)
                for _, row in h_df.iterrows():
                    friendly = FIELD_LABELS.get(str(row.get("Field", "")), str(row.get("Field", "")))
                    edit_rows.append({
                        "#":          "",
                        "Action":     f"✏️ {friendly} updated",
                        "Changed By": row.get("Edited_By", ""),
                        "Date":       row.get("Edit_Date", ""),
                        "Time":       row.get("Edit_Time", ""),
                        "From":       row.get("Old_Value", ""),
                        "To":         row.get("New_Value", ""),
                    })

            created_row = {
                "#":          "",
                "Action":     "🆕 Record Created",
                "Changed By": str(sel_rec.get("Created_By", "—")),
                "Date":       str(sel_rec.get("Entry_Date", "—")),
                "Time":       str(sel_rec.get("Entry_Time", "—")) if "Entry_Time" in sel_rec else "—",
                "From":       "",
                "To":         "",
            }

            hist_display = pd.DataFrame([created_row] + edit_rows).reset_index(drop=True)
            hist_display.index += 1
            hist_display["#"] = hist_display.index
            st.dataframe(hist_display, use_container_width=True, hide_index=True)

        except Exception as ex:
            st.warning(f"Could not load history: {ex}")
    else:
        st.divider()
        st.caption("🕓 Click a record in the table above to view its edit history.")

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
