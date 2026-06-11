"""
DocRegistry Pro - Main Application
Version: 2.2
Developer: Achyutam Mehta
"""

import os
import streamlit as st
import extra_streamlit_components as stx
from utils.simple_auth import SimpleAuth
from utils.sheets_manager import SheetsManager
from utils.email_sender import notify_admins_new_request, notify_user_registration_received, notify_user_request_status, send_password_reminder
from utils.telegram_sender import should_send_daily_appointments, mark_daily_appointments_sent, notify_today_appointments
from datetime import datetime, date, timedelta, time
import yaml
import pandas as pd

# =====================================================
# PAGE CONFIG — must be the very first st call
# =====================================================
st.set_page_config(
    page_title="DocRegistry Pro",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Instantiate CookieManager ONCE per script run — after set_page_config
_cookie_manager = stx.CookieManager(key="docregistry_auth_cm")

# =====================================================
# UTILITIES
# =====================================================
def clean_text(value: str) -> str:
    return " ".join(value.strip().split())

def safe_index(options, value, default=0):
    try:
        return options.index(str(value))
    except ValueError:
        return default

# Column name mapping — sheet names → display names
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

def display_df(df):
    """Return a copy of df with sheet column names replaced by display names."""
    return df.rename(columns=COL_DISPLAY)

st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# LOAD CONFIG
# =====================================================
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

DOCUMENT_TYPES       = config.get("document_types", [])
PARTY_NAME_2_OPTIONS = config.get("party_name_2_options", [])
DUPLICATE_CONFIG     = config.get("duplicate_check", {})
SRO_CONFIG           = config.get("sro_options", {})   # dict: {district: [sro, ...]}
SRO_ALL_FLAT         = [sro for sros in SRO_CONFIG.values() for sro in sros]
STATUS_OPTIONS       = ["Pending", "In Progress", "Completed", "Rejected"]

# =====================================================
# AUTH
# =====================================================
auth = SimpleAuth("config.yaml", cookie_manager=_cookie_manager)

if not auth.is_authenticated():
    _app_cfg = config.get("app", {})
    st.title(f"🏛️ {_app_cfg.get('name', 'DocRegistry Pro')}")
    st.subheader(f"{_app_cfg.get('company', 'BK Mehta & Associates')} — {_app_cfg.get('tagline', 'Advocate Office Registry Management System')}")

    # Show login directly after a successful request submission
    if st.session_state.pop("request_submitted", None):
        st.success("✅ Your request has been submitted! Please wait for admin approval. You can log in once approved.")
        auth.login()
        st.stop()

    # Show login directly after password reminder is sent
    if st.session_state.pop("fp_success", None):
        st.success("✅ Password sent! Please check your email inbox.")
        auth.login()
        st.stop()

    tab_login, tab_signup, tab_forgot = st.tabs(["🔐 Login", "📝 Request Access", "🔑 Forgot Password"])

    with tab_login:
        auth.login()

    with tab_forgot:
        st.markdown("### 🔑 Forgot Password")
        st.caption("Enter your username and registered email. We will send your password to that email.")
        with st.form("forgot_form"):
            fp_username = st.text_input("Username *", placeholder="Enter your username")
            fp_email    = st.text_input("Registered Email *", placeholder="Enter your registered email")
            fp_submit   = st.form_submit_button("📧 Send Password", type="primary", use_container_width=True)

        if fp_submit:
            if not fp_username.strip() or not fp_email.strip():
                st.error("❌ Both username and email are required.")
            elif not auth.username_exists(fp_username.strip()):
                st.error("❌ Your details do not match our records. Please check your username and email.")
            else:
                try:
                    _fp_sm      = SheetsManager()
                    _reg_email  = _fp_sm.get_user_email_from_requests(fp_username.strip())
                    _user_data  = auth.users.get(fp_username.strip(), {})
                    if _reg_email.lower() == fp_email.strip().lower():
                        send_password_reminder(
                            to_email  = _reg_email,
                            full_name = _user_data.get("name", fp_username.strip()),
                            username  = fp_username.strip(),
                            password  = _user_data.get("password", ""),
                        )
                        st.session_state["fp_success"] = True
                        st.rerun()
                    else:
                        st.error("❌ Your details do not match our records. Please check your username and email.")
                except Exception as _fp_ex:
                    st.error(f"❌ Could not send email: {_fp_ex}")

    with tab_signup:
        st.markdown("### Request a New Account")
        st.caption("Fill in your details. Admin will review and approve your request.")
        with st.form("signup_form"):
            su_username  = st.text_input("Username *", placeholder="e.g., parag")
            su_fullname  = st.text_input("Full Name *", placeholder="e.g., Parag Mehta")
            su_email     = st.text_input("Email", placeholder="e.g., parag@example.com")
            su_role      = st.selectbox("Role *", ["Staff", "Admin"])
            su_password  = st.text_input("Password *", type="password")
            su_confirm   = st.text_input("Confirm Password *", type="password")
            su_submit    = st.form_submit_button("📤 Submit Request", type="primary", use_container_width=True)

        if su_submit:
            if not su_username.strip() or not su_fullname.strip() or not su_password:
                st.error("❌ Username, Full Name and Password are required.")
            elif su_password != su_confirm:
                st.error("❌ Passwords do not match.")
            elif auth.username_exists(su_username.strip()):
                st.error("❌ Username already exists. Please choose another.")
            else:
                try:
                    _sm = SheetsManager()
                    from datetime import datetime as _dt
                    _requested_date = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                    _sm.add_user_request(
                        username=su_username.strip(),
                        full_name=su_fullname.strip(),
                        email=su_email.strip(),
                        role=su_role.lower(),
                        password=su_password
                    )
                    # Notify all admins (non-blocking)
                    try:
                        _admin_emails = config.get("email", {}).get("admin_emails", ["bkmehta.associate@gmail.com"])
                        notify_admins_new_request(
                            admin_emails=_admin_emails,
                            full_name=su_fullname.strip(),
                            username=su_username.strip(),
                            role=su_role,
                            email=su_email.strip(),
                            requested_date=_requested_date,
                        )
                    except Exception as _mail_ex:
                        st.warning(f"⚠️ Request saved but admin notification email could not be sent: {_mail_ex}")
                    # Send confirmation email to the registering user
                    if su_email.strip():
                        try:
                            notify_user_registration_received(
                                to_email=su_email.strip(),
                                full_name=su_fullname.strip(),
                                username=su_username.strip(),
                            )
                        except Exception:
                            pass
                    # Redirect to login page with success banner
                    st.session_state["request_submitted"] = True
                    st.rerun()
                except Exception as ex:
                    st.error(f"❌ Could not submit request: {ex}")

    st.stop()

# =====================================================
# SESSION
# =====================================================
user_info = auth.get_user_info()
username  = st.session_state.username

# =====================================================
# SIDEBAR — NAVIGATION
# =====================================================
st.sidebar.title("🏠 DocRegistry Pro")
st.sidebar.markdown(f"👋 **{user_info['name']}**")
st.sidebar.markdown(f"Role: **{user_info['role'].title()}**")

_nav = ["🏠 Dashboard", "📝 New Entry", "🔍 Search Records", "✏️ Edit Records"]
if user_info.get("role") == "admin":
    _nav.append("👥 User Management")

page = st.sidebar.radio("Navigation", _nav, label_visibility="collapsed", key="nav_page")

if st.sidebar.button("🚪 Logout", type="primary", use_container_width=True):
    auth.logout()

# =====================================================
# INIT GOOGLE SHEETS
# =====================================================
sheets_manager = SheetsManager()

# =====================================================
# DAILY "TODAY'S APPOINTMENTS" TELEGRAM NOTIFICATION
# =====================================================
if should_send_daily_appointments():
    try:
        _today_appts = sheets_manager.get_appointments_for_date()
        notify_today_appointments(_today_appts.to_dict("records"))
        mark_daily_appointments_sent()
    except Exception:
        pass


# =====================================================
# DASHBOARD
# =====================================================
if page == "🏠 Dashboard":

    st.title("🏛️ Dashboard")
    st.markdown(f"👋 **Welcome back, {user_info['name']}!**  \nHere's a quick overview of appointments and recent registry activity.")

    df = sheets_manager.get_all_records()

    if df.empty:
        st.info("No records available yet.")
        st.stop()

    # Today's Appointments
    st.divider()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📅 Today's Appointments")
    with col2:
        today_csv = df[df["Appointment Date"] == date.today().strftime("%Y-%m-%d")]
        st.download_button("⬇️", today_csv.to_csv(index=False),
                           file_name="todays_appointments.csv",
                           help="Download Today's Appointments",
                           use_container_width=True)

    today_df = df[df["Appointment Date"] == date.today().strftime("%Y-%m-%d")]
    if not today_df.empty:
        st.dataframe(display_df(today_df.sort_values("Appointment Time")), use_container_width=True)
    else:
        st.info("No appointments scheduled for today.")

    # Upcoming Appointments (7 Days)
    st.divider()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📆 Upcoming Appointments (Next 7 Days)")
    with col2:
        upcoming_df = df[
            (df["Appointment Date"] > date.today().strftime("%Y-%m-%d")) &
            (df["Appointment Date"] <= (date.today() + timedelta(days=7)).strftime("%Y-%m-%d"))
        ]
        st.download_button("⬇️", upcoming_df.to_csv(index=False),
                           file_name="upcoming_appointments_7_days.csv",
                           help="Download Upcoming Appointments",
                           use_container_width=True)

    if not upcoming_df.empty:
        st.dataframe(display_df(upcoming_df.sort_values(["Appointment Date", "Appointment Time"])), use_container_width=True)
    else:
        st.info("No upcoming appointments in the next 7 days.")

    # Record View
    st.divider()
    st.subheader("👤 Record View")
    view_mode   = st.radio("Select Records", ["All Records", "My Records"], horizontal=True)
    filtered_df = df.copy()
    if view_mode == "My Records":
        filtered_df = filtered_df[filtered_df["Created_By"] == username]

        # My Records summary strip
        my_total      = len(filtered_df)
        my_pending    = len(filtered_df[filtered_df["Title_Status"].str.lower() == "pending"])
        my_inprogress = len(filtered_df[filtered_df["Title_Status"].str.lower() == "in progress"])
        my_completed  = len(filtered_df[filtered_df["Title_Status"].str.lower() == "completed"])

        st.markdown(f"""
        <div style="background:#eef6ff;border:1px solid #c2dbf7;border-radius:10px;
                    padding:14px 20px;margin:10px 0 4px 0;font-size:14px">
            👤 <strong>{user_info['name']}</strong> has added
            <strong style="font-size:18px;color:#1565C0">{my_total}</strong> record(s) in total &nbsp;·&nbsp;
            ⏳ Pending: <strong>{my_pending}</strong> &nbsp;·&nbsp;
            🔄 In Progress: <strong>{my_inprogress}</strong> &nbsp;·&nbsp;
            ✅ Completed: <strong>{my_completed}</strong>
        </div>
        """, unsafe_allow_html=True)

    # Records table
    st.divider()
    col1, col2 = st.columns([3, 1])

    if view_mode == "My Records":
        table_df    = filtered_df.sort_values("Entry_ID", ascending=False).head(10)
        table_label = "📄 My Latest Records"
        table_cap   = ""
    else:
        # All appointments in the current month, sorted by appointment date
        _cur_month   = date.today().strftime("%Y-%m")
        _appt_series = pd.to_datetime(filtered_df["Appointment Date"], errors="coerce")
        _in_month    = _appt_series.dt.strftime("%Y-%m") == _cur_month
        upcoming     = filtered_df[_in_month].copy()
        upcoming["_appt_sort"] = pd.to_datetime(upcoming["Appointment Date"], errors="coerce")
        table_df     = upcoming.sort_values("_appt_sort").drop(columns=["_appt_sort"])
        _month_name  = date.today().strftime("%B %Y")
        table_label  = f"📅 Appointments — {_month_name}"
        table_cap    = f"{len(table_df)} appointment(s) this month"

    with col1:
        st.subheader(table_label)
        if table_cap:
            st.caption(table_cap)
    with col2:
        st.download_button("⬇️ Download CSV", table_df.to_csv(index=False),
                           file_name="appointments_this_month.csv",
                           mime="text/csv",
                           use_container_width=True)

    if table_df.empty:
        st.info("No appointments found for this month.")
    else:
        st.dataframe(display_df(table_df), use_container_width=True, height=300)

    # Status Overview
    st.divider()
    st.subheader("📊 Status Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📚 Total",       len(filtered_df))
    col2.metric("⏳ Pending",     len(filtered_df[filtered_df["Title_Status"].str.lower() == "pending"]))
    col3.metric("🔄 In Progress", len(filtered_df[filtered_df["Title_Status"].str.lower() == "in progress"]))
    col4.metric("✅ Completed",   len(filtered_df[filtered_df["Title_Status"].str.lower() == "completed"]))
    st.bar_chart(filtered_df["Title_Status"].value_counts())

    # =========================================================
    # ENHANCEMENT 1 — PENDING RECORDS ALERT
    # =========================================================
    st.divider()
    st.subheader("⚠️ Pending Records Alert")
    st.caption("All records currently in Pending status, sorted by oldest first.")

    pending_all = df[df["Title_Status"].str.lower() == "pending"].copy()
    pending_all["Entry_Date_dt"] = pd.to_datetime(pending_all["Entry_Date"], errors="coerce")
    today_ts = pd.Timestamp.today().normalize()
    pending_all["Days Pending"] = (today_ts - pending_all["Entry_Date_dt"]).dt.days

    if pending_all.empty:
        st.success("✅ No records are currently in Pending status.")
    else:
        long_pending = pending_all.sort_values("Days Pending", ascending=False)
        over_30 = int((long_pending["Days Pending"] > 30).sum())
        if over_30:
            st.warning(f"⚠️ {over_30} record(s) pending for over 30 days — {len(long_pending)} pending total.")
        else:
            st.info(f"ℹ️ {len(long_pending)} record(s) currently pending.")

        # All sheet columns + Days Pending — drop internal datetime helper
        all_sheet_cols = [
            "Entry_ID", "Doc_Type", "Appointment Date", "Appointment Time",
            "SRO", "Party_Name 1", "Party_Name 1 Mobile_No", "Party_Name 2",
            "Garvi_Application_ID", "Inedex_Application_No", "Index_No",
            "Search_No", "Title_Status", "Created_By", "Entry_Date", "Entry_Time",
            "Days Pending"
        ]
        alert_cols = [c for c in all_sheet_cols if c in long_pending.columns]
        dl_df = long_pending[alert_cols].reset_index(drop=True)

        pa_col1, pa_col2 = st.columns([4, 1])
        with pa_col2:
            st.download_button(
                "⬇️ Download CSV",
                data=dl_df.to_csv(index=False),
                file_name="pending_records.csv",
                mime="text/csv",
                use_container_width=True
            )
        st.dataframe(display_df(dl_df), use_container_width=True)

    # =========================================================
    # ENHANCEMENT 2 — MONTHLY BREAKDOWN (DROPDOWN)
    # =========================================================
    st.divider()
    st.subheader("📈 Monthly Breakdown")
    st.caption("Select date type and month to compare daily activity.")

    mb_col1, mb_col2 = st.columns([2, 3])
    with mb_col1:
        date_type = st.radio(
            "View by",
            ["Appointment Date", "Entry Date"],
            horizontal=True,
            key="mb_date_type"
        )
    date_col = "Appointment Date" if date_type == "Appointment Date" else "Entry_Date"

    # Build list of available months from selected date column
    df["_appt_dt"] = pd.to_datetime(df[date_col], errors="coerce")
    available_months = (
        df["_appt_dt"].dropna()
        .dt.to_period("M")
        .unique()
    )
    available_months = sorted(available_months, reverse=True)   # newest first

    if not available_months:
        st.info("No appointment dates found to build monthly chart.")
    else:
        month_labels = [m.strftime("%B %Y") for m in available_months]
        month_keys   = [str(m) for m in available_months]          # "2026-06"

        sel_label = st.selectbox(
            "Select Month",
            month_labels,
            key="dash_month_select"
        )
        sel_key = month_keys[month_labels.index(sel_label)]        # "2026-06"

        sel_month_df = df[
            df["_appt_dt"].dt.to_period("M").astype(str) == sel_key
        ].copy()

        if sel_month_df.empty:
            st.info(f"No records found for {sel_label}.")
        else:
            sel_month_df["_day"] = sel_month_df["_appt_dt"].dt.strftime("%d %b")

            # Bar chart: records per day broken down by status
            trend = (
                sel_month_df.groupby(["_day", "Title_Status"])
                .size()
                .reset_index(name="Count")
                .pivot(index="_day", columns="Title_Status", values="Count")
                .fillna(0)
                .astype(int)
                .sort_index()
            )
            st.bar_chart(trend, use_container_width=True, height=280)

            # Summary metrics in a row
            m_cols = st.columns(4)
            m_cols[0].metric("Total",       len(sel_month_df))
            m_cols[1].metric("Pending",     int((sel_month_df["Title_Status"].str.lower() == "pending").sum()))
            m_cols[2].metric("In Progress", int((sel_month_df["Title_Status"].str.lower() == "in progress").sum()))
            m_cols[3].metric("Completed",   int((sel_month_df["Title_Status"].str.lower() == "completed").sum()))

    df.drop(columns=["_appt_dt"], inplace=True, errors="ignore")

    # =========================================================
    # ENHANCEMENT 3 — STAFF PERFORMANCE (ADMIN ONLY)
    # =========================================================
    if user_info.get("role") == "admin":
        st.divider()
        st.subheader("👥 Staff Performance")

        # Build filter options
        all_users  = sorted(df["Created_By"].dropna().unique().tolist())
        df["_edt"] = pd.to_datetime(df["Entry_Date"], errors="coerce")
        sp_months  = sorted(
            df["_edt"].dropna().dt.to_period("M").unique(),
            reverse=True
        )
        sp_month_labels = ["All Time"] + [m.strftime("%B %Y") for m in sp_months]
        sp_month_keys   = ["all"]      + [str(m) for m in sp_months]
        df.drop(columns=["_edt"], inplace=True, errors="ignore")

        sp_col1, sp_col2 = st.columns(2)
        with sp_col1:
            sel_user = st.selectbox(
                "Select Staff Member",
                ["All Users"] + all_users,
                key="sp_user"
            )
        with sp_col2:
            sel_month_label = st.selectbox(
                "Select Month",
                sp_month_labels,
                key="sp_month"
            )
        sel_month_key = sp_month_keys[sp_month_labels.index(sel_month_label)]

        # Filter data
        sp_df = df.copy()
        if sel_user != "All Users":
            sp_df = sp_df[sp_df["Created_By"] == sel_user]
        if sel_month_key != "all":
            sp_df = sp_df[
                pd.to_datetime(sp_df["Entry_Date"], errors="coerce")
                .dt.to_period("M").astype(str) == sel_month_key
            ]

        if sp_df.empty:
            st.info("No records found for the selected filters.")
        else:
            # Summary table grouped by user
            staff_perf = (
                sp_df.groupby("Created_By")
                .apply(lambda x: pd.Series({
                    "Total":       len(x),
                    "Pending":     (x["Title_Status"].str.lower() == "pending").sum(),
                    "In Progress": (x["Title_Status"].str.lower() == "in progress").sum(),
                    "Completed":   (x["Title_Status"].str.lower() == "completed").sum(),
                }), include_groups=False)
                .reset_index()
                .rename(columns={"Created_By": "Staff Member"})
                .sort_values("Total", ascending=False)
            )
            staff_perf[["Total","Pending","In Progress","Completed"]] = \
                staff_perf[["Total","Pending","In Progress","Completed"]].astype(int)

            st.dataframe(staff_perf, use_container_width=True, hide_index=True)

            # Stacked bar — Pending / In Progress / Completed per staff member
            chart_cols = [c for c in ["Pending", "In Progress", "Completed"] if c in staff_perf.columns]
            chart_data = staff_perf.set_index("Staff Member")[chart_cols]
            bc_col, _ = st.columns([2, 1])
            with bc_col:
                st.bar_chart(chart_data, height=280)

            # If single user selected, show their actual records
            if sel_user != "All Users":
                with st.expander(f"📄 View {sel_user}'s Records ({len(sp_df)})"):
                    show_cols = ["Entry_ID","Doc_Type","Appointment Date","SRO",
                                 "Party_Name 1","Title_Status","Entry_Date"]
                    show_cols = [c for c in show_cols if c in sp_df.columns]
                    st.dataframe(
                        display_df(sp_df[show_cols].sort_values("Entry_Date", ascending=False).reset_index(drop=True)),
                        use_container_width=True
                    )

# =====================================================
# NEW ENTRY
# =====================================================
elif page == "📝 New Entry":
    st.switch_page("pages/1_📝_New_Entry.py")

# =====================================================
# SEARCH RECORDS
# =====================================================
elif page == "🔍 Search Records":

    st.title("🔍 Search Records")
    st.markdown("Search and filter registry entries from the database")
    st.divider()

    df = sheets_manager.get_all_records()

    if df.empty:
        st.info("No records found in the database.")
        st.stop()

    # Counter key to reset all filter widgets
    if "search_filter_key" not in st.session_state:
        st.session_state["search_filter_key"] = 0
    fk = st.session_state["search_filter_key"]

    # Search & Filter Panel
    with st.expander("🔎 Search & Filters", expanded=True):
        col1, col2, col_search, col_clear = st.columns([3, 3, 1, 1])
        with col1:
            keyword = st.text_input(
                "Search by Party Name / Entry ID / GARVI No / Index No",
                placeholder="Type to search...",
                key=f"search_keyword_{fk}"
            )
        with col2:
            status_filter = st.multiselect("Title Status", options=STATUS_OPTIONS, default=[], key=f"status_filter_{fk}")
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
            doc_type_filter = st.multiselect("Document Type", options=DOCUMENT_TYPES, default=[], key=f"doc_type_filter_{fk}")
        with col4:
            sro_filter = st.multiselect("SRO", options=sorted(SRO_ALL_FLAT), default=[], key=f"sro_filter_{fk}")
        with col5:
            party2_filter = st.multiselect("Party Name 2", options=PARTY_NAME_2_OPTIONS, default=[], key=f"party2_filter_{fk}")

        col6, col7 = st.columns(2)
        with col6:
            date_from = st.date_input("Appointment Date From", value=None, key=f"date_from_{fk}")
        with col7:
            date_to = st.date_input("Appointment Date To", value=None, key=f"date_to_{fk}")

    # Apply Filters
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

    # Summary Metrics
    st.divider()
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Total Results", len(filtered))
    col_b.metric("Pending",     len(filtered[filtered["Title_Status"].str.lower() == "pending"])     if not filtered.empty else 0)
    col_c.metric("In Progress", len(filtered[filtered["Title_Status"].str.lower() == "in progress"]) if not filtered.empty else 0)
    col_d.metric("Completed",   len(filtered[filtered["Title_Status"].str.lower() == "completed"])   if not filtered.empty else 0)

    st.divider()

    # Results Table
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

        # ── Record History on row click ────────────────────────
        selected_rows = table_event.selection.rows
        if selected_rows:
            sel_idx = selected_rows[0]
            sel_rec = result_df.iloc[sel_idx]
            selected_entry_id = str(sel_rec.get("Entry_ID", "")).replace(",", "")

            st.divider()
            st.subheader(f"🕓 Edit History — {sel_rec.get('Party_Name 1', '')} | {sel_rec.get('Doc_Type', '')} | {sel_rec.get('Appointment Date', '')}")

            SR_FIELD_LABELS = {
                "Doc_Type": "Document Type", "Appointment Date": "Appointment Date",
                "Appointment Time": "Appointment Time", "SRO": "SRO",
                "Party_Name 1": "Party Name 1", "Party_Name 1 Mobile_No": "Party 1 Mobile No",
                "Party_Name 2": "Party Name 2", "Garvi_Application_ID": "GARVI App. No.",
                "Inedex_Application_No": "Index App. No.", "Index_No": "Index No.",
                "Search_No": "Search No.", "Title_Status": "Title Status",
            }
            try:
                h_df = sheets_manager.get_history(selected_entry_id)
                edit_rows = []
                if not h_df.empty:
                    h_df["Entry_ID"] = h_df["Entry_ID"].astype(str).str.replace(",", "", regex=False)
                    for _, row in h_df.iterrows():
                        friendly = SR_FIELD_LABELS.get(str(row.get("Field", "")), str(row.get("Field", "")))
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
                    "Time":       str(sel_rec.get("Entry_Time", "—")),
                    "From": "", "To": "",
                }
                import pandas as _pd
                hist_display = _pd.DataFrame([created_row] + edit_rows).reset_index(drop=True)
                hist_display.index += 1
                hist_display["#"] = hist_display.index
                st.dataframe(hist_display, use_container_width=True, hide_index=True)
            except Exception as ex:
                st.warning(f"Could not load history: {ex}")
        else:
            st.divider()
            st.caption("🕓 Click a record in the table above to view its edit history.")

# =====================================================
# EDIT RECORDS
# =====================================================
elif page == "✏️ Edit Records":

    st.title("✏️ Edit Records")
    st.markdown("Search by Entry ID or GARVI Application ID to load and update a record.")
    st.divider()

    # Display save result message carried over from the post-save rerun
    if "_edit_save_result" in st.session_state:
        kind, msg = st.session_state.pop("_edit_save_result")
        if kind == "success":
            st.success(msg)
        elif kind == "warning":
            st.warning(msg)
        else:
            st.info(msg)

    df = sheets_manager.get_all_records()

    # Counter-based key so we can reset the widget after save
    if "edit_form_key" not in st.session_state:
        st.session_state["edit_form_key"] = 0

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

    def _norm_time(v):
        """Normalize any time representation to HH:MM:SS — handles "10:30", "10:30:00", and float fractions."""
        try:
            s = str(v).strip()
            if not s or s in ("None", "nan"):
                return ""
            if ":" in s:
                p = s.split(":")
                h = int(float(p[0]))
                m = int(float(p[1])) if len(p) > 1 else 0
                return f"{h:02d}:{m:02d}:00"
            frac = float(s)
            if 0.0 <= frac <= 1.0:
                total_s = round(frac * 86400)
                h, m = divmod(total_s // 60, 60)
                return f"{h:02d}:{m:02d}:00"
        except Exception:
            pass
        return str(v)

    # Search by Entry ID or GARVI Application ID
    col_type, col_search, col_btn = st.columns([2, 4, 1])
    with col_type:
        search_by = st.selectbox(
            "Search By",
            ["GARVI Application ID", "Entry ID"],
            key=f"edit_search_by_{st.session_state['edit_form_key']}"
        )
    with col_search:
        search_placeholder = "e.g., 20250515143022" if search_by == "Entry ID" else "e.g., 20261100843645"
        edit_entry_id = st.text_input(
            f"Enter {search_by}",
            placeholder=search_placeholder,
            key=f"edit_entry_id_{st.session_state['edit_form_key']}"
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        load_btn = st.button("🔍 Load Record", use_container_width=True)

    edit_rec = None
    if edit_entry_id.strip():
        if search_by == "Entry ID":
            match = df[df["Entry_ID"].astype(str) == edit_entry_id.strip()]
        else:
            match = df[df["Garvi_Application_ID"].astype(str) == edit_entry_id.strip()]
        if match.empty:
            st.warning(f"No record found with {search_by}: `{edit_entry_id.strip()}`")
        else:
            edit_rec = match.iloc[0]
            # Snapshot the values as-loaded from Sheets so that after save_btn fires
            # (and get_all_records() returns the already-updated row), we still
            # compare against the ORIGINAL values the user saw when they opened the form.
            _snap_key = f"pre_edit_snap_{st.session_state['edit_form_key']}"
            if _snap_key not in st.session_state:
                st.session_state[_snap_key] = {
                    "Doc_Type":               str(edit_rec.get("Doc_Type", "")),
                    "Appointment Date":        str(edit_rec.get("Appointment Date", "")),
                    "Appointment Time":        _norm_time(edit_rec.get("Appointment Time", "")),
                    "SRO":                    str(edit_rec.get("SRO", "")),
                    "Party_Name 1":           str(edit_rec.get("Party_Name 1", "")),
                    "Party_Name 1 Mobile_No": str(edit_rec.get("Party_Name 1 Mobile_No", "")),
                    "Party_Name 2":           str(edit_rec.get("Party_Name 2", "") or ""),
                    "Garvi_Application_ID":   str(edit_rec.get("Garvi_Application_ID", "")),
                    "Inedex_Application_No":  str(edit_rec.get("Inedex_Application_No", "")),
                    "Index_No":               str(edit_rec.get("Index_No", "")),
                    "Search_No":              str(edit_rec.get("Search_No", "")),
                    "Title_Status":           str(edit_rec.get("Title_Status", "")),
                }

    if edit_rec is not None:
        party1_val = edit_rec.get("Party_Name 1", "")
        party2_val = edit_rec.get("Party_Name 2", "") or "—"
        st.success(
            f"Record loaded — "
            f"Party 1: **{party1_val}** | "
            f"Party 2: **{party2_val}** | "
            f"Status: **{edit_rec.get('Title_Status', '')}** | "
            f"Doc: **{edit_rec.get('Doc_Type', '')}**"
        )

        # Compact info strip
        st.markdown("""
        <style>
        .rec-card{background:#f8f9fa;border:1px solid #e0e0e0;border-radius:8px;
                  padding:8px 12px;font-size:13px;line-height:1.5}
        .rec-card .label{color:#888;font-size:11px;font-weight:600;
                         text-transform:uppercase;letter-spacing:.5px}
        .rec-card .value{color:#1a1a1a;font-size:13px;font-weight:500;
                         word-break:break-all}
        </style>
        """, unsafe_allow_html=True)

        card_items = [
            ("Entry ID",   str(edit_rec.get("Entry_ID", "")).replace(",", "")),
            ("Doc Type",   str(edit_rec.get("Doc_Type", ""))),
            ("Date",       str(edit_rec.get("Appointment Date", ""))),
            ("SRO",        str(edit_rec.get("SRO", ""))),
            ("Status",     str(edit_rec.get("Title_Status", ""))),
            ("Created By", str(edit_rec.get("Created_By", ""))),
        ]
        cols = st.columns(6)
        for col, (label, value) in zip(cols, card_items):
            col.markdown(
                f'<div class="rec-card">'
                f'<div class="label">{label}</div>'
                f'<div class="value">{value}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        st.divider()

        # District & SRO outside the form so they react instantly on change
        existing_sro = str(edit_rec.get("SRO", ""))
        pre_district = next(
            (d for d, sros in SRO_CONFIG.items() if existing_sro in sros),
            list(SRO_CONFIG.keys())[0] if SRO_CONFIG else ""
        )

        def _on_edit_district_change():
            st.session_state["e_sro"] = None

        ec1, ec2 = st.columns(2)
        with ec1:
            e_district = st.selectbox(
                "District *",
                list(SRO_CONFIG.keys()),
                index=safe_index(list(SRO_CONFIG.keys()), pre_district),
                key="e_district",
                on_change=_on_edit_district_change
            )
        with ec2:
            cur_edit_district = st.session_state.get("e_district", pre_district)
            district_sros     = SRO_CONFIG.get(cur_edit_district, [])
            e_sro = st.selectbox(
                "SRO *",
                district_sros,
                index=safe_index(district_sros, existing_sro),
                key="e_sro"
            )

        with st.form("edit_form"):
            st.markdown("### 📋 Entry Details")
            c1, c2 = st.columns(2)
            with c1:
                e_doc_type = st.selectbox(
                    "Document Type *", DOCUMENT_TYPES,
                    index=safe_index(DOCUMENT_TYPES, edit_rec.get("Doc_Type", "")),
                    key="e_doc_type"
                )
            with c2:
                try:
                    e_date = st.date_input(
                        "Date *",
                        value=date.fromisoformat(str(edit_rec.get("Appointment Date", date.today()))),
                        key="e_date"
                    )
                except Exception:
                    e_date = st.date_input("Date *", value=date.today(), key="e_date")

            try:
                t_parts = str(edit_rec.get("Appointment Time", "10:00")).split(":")
                e_time = st.time_input(
                    "Time *",
                    value=time(int(t_parts[0]), int(t_parts[1])),
                    key="e_time"
                )
            except Exception:
                e_time = st.time_input("Time *", value=time(10, 0), key="e_time")

            st.markdown("### 👥 Party Information")
            c1, c2 = st.columns(2)
            with c1:
                e_party1 = st.text_input(
                    "Party Name 1 *",
                    value=str(edit_rec.get("Party_Name 1", "")),
                    key="e_party1"
                )
            with c2:
                e_party1_mobile = st.text_input(
                    "Party 1 Mobile No",
                    value=str(edit_rec.get("Party_Name 1 Mobile_No", "")),
                    key="e_party1_mobile"
                )

            p2_opts = ["-- Select --"] + PARTY_NAME_2_OPTIONS
            e_party2 = st.selectbox(
                "Party Name 2", p2_opts,
                index=safe_index(p2_opts, edit_rec.get("Party_Name 2", "-- Select --")),
                key="e_party2"
            )

            st.markdown("### 📂 Application Details")
            c1, c2, c3 = st.columns(3)
            with c1:
                e_garvi = st.text_input(
                    "GARVI App. No.",
                    value=str(edit_rec.get("Garvi_Application_ID", "")),
                    placeholder="ex. 20261100843645",
                    key="e_garvi"
                )
            with c2:
                e_index_appli = st.text_input(
                    "Index App. No.",
                    value=str(edit_rec.get("Inedex_Application_No", "")),
                    placeholder="ex. 80120260372851",
                    key="e_index_appli"
                )
            with c3:
                e_search = st.text_input(
                    "Search No.",
                    value=str(edit_rec.get("Search_No", "")),
                    placeholder="ex. 202612030719415",
                    key="e_search"
                )

            c1, c2 = st.columns(2)
            with c1:
                e_index_no = st.text_input(
                    "Index No.",
                    value=str(edit_rec.get("Index_No", "")),
                    placeholder="ex. 9729-2026",
                    key="e_index_no"
                )
            with c2:
                e_status = st.selectbox(
                    "Title Status *", STATUS_OPTIONS,
                    index=safe_index(STATUS_OPTIONS, edit_rec.get("Title_Status", "Pending")),
                    key="e_status"
                )

            st.markdown("---")
            save_btn = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)

        # Always use the real Entry ID from the loaded record — not the search value
        # (user may have searched by GARVI ID)
        real_entry_id = str(edit_rec.get("Entry_ID", "")).replace(",", "")

        col_save, col_clear = st.columns([4, 1])
        with col_clear:
            if st.button("🔄 Load Another Record", use_container_width=True, key="clear_btn"):
                st.session_state.pop("just_saved_id", None)
                st.session_state["edit_form_key"] += 1
                st.rerun()

        if save_btn:
            e_district = st.session_state.get("e_district", "")
            e_sro      = st.session_state.get("e_sro", "")
            if not e_party1.strip():
                st.error("❌ Party Name 1 is required.")
            else:
                try:
                    new_party2 = e_party2 if e_party2 != "-- Select --" else ""

                    ok = sheets_manager.update_record(
                        entry_id=real_entry_id,
                        doc_type=e_doc_type,
                        appointment_date=str(e_date),
                        appointment_time=str(e_time),
                        sro=e_sro,
                        party_name_1=e_party1.strip(),
                        party1_mobile=e_party1_mobile.strip(),
                        party_name_2=new_party2,
                        garvi_application_id=e_garvi.strip(),
                        index_application_no=e_index_appli.strip(),
                        index_no=e_index_no.strip(),
                        search_no=e_search.strip(),
                        title_status=e_status
                    )

                    if ok:
                        # Use the pre-edit snapshot so we compare against values the user
                        # saw when they opened the form — not the already-updated row that
                        # get_all_records() would return after the update above.
                        _snap_key = f"pre_edit_snap_{st.session_state['edit_form_key']}"
                        _snap = st.session_state.get(_snap_key, {})
                        field_map = [
                            ("Doc_Type",               _snap.get("Doc_Type",               str(edit_rec.get("Doc_Type", ""))),               e_doc_type),
                            ("Appointment Date",        _snap.get("Appointment Date",        str(edit_rec.get("Appointment Date", ""))),        str(e_date)),
                            ("Appointment Time",        _snap.get("Appointment Time",        _norm_time(edit_rec.get("Appointment Time", ""))), _norm_time(e_time)),
                            ("SRO",                    _snap.get("SRO",                    str(edit_rec.get("SRO", ""))),                    e_sro),
                            ("Party_Name 1",           _snap.get("Party_Name 1",           str(edit_rec.get("Party_Name 1", ""))),           e_party1.strip()),
                            ("Party_Name 1 Mobile_No", _snap.get("Party_Name 1 Mobile_No", str(edit_rec.get("Party_Name 1 Mobile_No", ""))), e_party1_mobile.strip()),
                            ("Party_Name 2",           _snap.get("Party_Name 2",           str(edit_rec.get("Party_Name 2", ""))),           new_party2),
                            ("Garvi_Application_ID",   _snap.get("Garvi_Application_ID",   str(edit_rec.get("Garvi_Application_ID", ""))),   e_garvi.strip()),
                            ("Inedex_Application_No",  _snap.get("Inedex_Application_No",  str(edit_rec.get("Inedex_Application_No", ""))),  e_index_appli.strip()),
                            ("Index_No",               _snap.get("Index_No",               str(edit_rec.get("Index_No", ""))),               e_index_no.strip()),
                            ("Search_No",              _snap.get("Search_No",              str(edit_rec.get("Search_No", ""))),               e_search.strip()),
                            ("Title_Status",           _snap.get("Title_Status",           str(edit_rec.get("Title_Status", ""))),           e_status),
                        ]
                        changes = [(f, old, new) for f, old, new in field_map if old != new]

                        # Always update snapshot to the just-saved values so the next
                        # edit on this same record compares against the correct baseline.
                        st.session_state[_snap_key] = {
                            "Doc_Type":               e_doc_type,
                            "Appointment Date":        str(e_date),
                            "Appointment Time":        _norm_time(e_time),
                            "SRO":                    e_sro,
                            "Party_Name 1":           e_party1.strip(),
                            "Party_Name 1 Mobile_No": e_party1_mobile.strip(),
                            "Party_Name 2":           new_party2,
                            "Garvi_Application_ID":   e_garvi.strip(),
                            "Inedex_Application_No":  e_index_appli.strip(),
                            "Index_No":               e_index_no.strip(),
                            "Search_No":              e_search.strip(),
                            "Title_Status":           e_status,
                        }

                        if changes:
                            try:
                                sheets_manager.log_history(real_entry_id, username, changes)
                                st.toast(f"✅ Record {real_entry_id} updated!", icon="✅")
                                st.session_state["_edit_save_result"] = (
                                    "success",
                                    f"✅ Record **{real_entry_id}** saved. "
                                    f"**{len(changes)} field(s)** changed — edit history updated below."
                                )
                            except Exception as log_ex:
                                st.toast(f"✅ Record {real_entry_id} updated!", icon="✅")
                                st.session_state["_edit_save_result"] = (
                                    "warning",
                                    f"⚠️ Record saved to sheet but history logging failed: {log_ex}"
                                )
                        else:
                            st.toast(f"✅ Record {real_entry_id} updated!", icon="✅")
                            st.session_state["_edit_save_result"] = (
                                "info",
                                "ℹ️ Record saved. No field values were changed — history not updated."
                            )

                        st.rerun()
                    else:
                        st.error(f"❌ Record not found in Google Sheets (Entry ID: `{real_entry_id}`).")
                except Exception as ex:
                    st.error(f"❌ Error updating record: {ex}")

        # Edit History viewer
        st.divider()
        st.subheader("🕓 Edit History")
        try:
            actual_entry_id = str(edit_rec.get("Entry_ID", "")).replace(",", "")
            hist_df = sheets_manager.get_history(actual_entry_id)

            # Build edit rows with friendly names and change description
            edit_rows = []
            if not hist_df.empty:
                hist_df["Entry_ID"] = hist_df["Entry_ID"].astype(str).str.replace(",", "", regex=False)
                for _, row in hist_df.iterrows():
                    friendly_field = FIELD_LABELS.get(str(row.get("Field", "")), str(row.get("Field", "")))
                    edit_rows.append({
                        "#":          "",
                        "Action":     f"✏️ {friendly_field} updated",
                        "Changed By": row.get("Edited_By", ""),
                        "Date":       row.get("Edit_Date", ""),
                        "Time":       row.get("Edit_Time", ""),
                        "From":       row.get("Old_Value", ""),
                        "To":         row.get("New_Value", ""),
                    })

            # First row: record created
            created_row = {
                "#":          "",
                "Action":     "🆕 Record Created",
                "Changed By": str(edit_rec.get("Created_By", "—")),
                "Date":       str(edit_rec.get("Entry_Date", "—")),
                "Time":       str(edit_rec.get("Entry_Time", "—")),
                "From":       "",
                "To":         "",
            }

            import pandas as pd
            history_display = pd.DataFrame(
                [created_row] + edit_rows
            ).reset_index(drop=True)
            history_display.index += 1
            history_display["#"] = history_display.index

            st.dataframe(history_display, use_container_width=True, hide_index=True)

        except Exception as ex:
            st.warning(f"Could not load history: {ex}")

# =====================================================
# USER MANAGEMENT (ADMIN ONLY)
# =====================================================
elif page == "👥 User Management":

    st.title("👥 User Management")
    st.markdown("Review and approve new account requests.")
    st.divider()

    tab_pending, tab_all, tab_users, tab_log = st.tabs(["⏳ Pending Requests", "📋 All Requests", "👤 Active Users", "🕓 Activity Log"])

    with tab_pending:
        try:
            pending_df = sheets_manager.get_user_requests(status="Pending")
            if pending_df.empty:
                st.success("✅ No pending requests.")
            else:
                st.warning(f"⏳ {len(pending_df)} pending request(s) awaiting approval.")
                for _, req in pending_df.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        with c1:
                            st.markdown(
                                f"**{req.get('Full_Name', '')}** (`{req.get('Username', '')}`)"
                                f"  —  Role: `{req.get('Role', '').title()}`"
                                f"  |  Email: {req.get('Email', '—')}"
                                f"  |  Requested: {req.get('Requested_Date', '—')}"
                            )
                        with c2:
                            if st.button("✅ Approve", key=f"approve_{req['Request_ID']}", use_container_width=True, type="primary"):
                                try:
                                    auth.add_user_to_config(
                                        username=str(req["Username"]),
                                        password=str(req["Password"]),
                                        name=str(req["Full_Name"]),
                                        role=str(req["Role"]).lower()
                                    )
                                    sheets_manager.update_request_status(
                                        str(req["Request_ID"]), "Approved", username
                                    )
                                    st.toast(f"✅ {req['Full_Name']} approved and added!", icon="✅")
                                    try:
                                        sheets_manager.log_user_activity(
                                            action="Approved",
                                            username=str(req.get("Username", "")),
                                            full_name=str(req.get("Full_Name", "")),
                                            role=str(req.get("Role", "")),
                                            performed_by=username,
                                        )
                                    except Exception:
                                        pass
                                    try:
                                        notify_user_request_status(
                                            to_email=str(req.get("Email", "")),
                                            full_name=str(req.get("Full_Name", "")),
                                            username=str(req.get("Username", "")),
                                            status="Approved",
                                        )
                                    except Exception:
                                        pass
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"❌ {ex}")
                        with c3:
                            if st.button("❌ Reject", key=f"reject_{req['Request_ID']}", use_container_width=True):
                                try:
                                    sheets_manager.update_request_status(
                                        str(req["Request_ID"]), "Rejected", username
                                    )
                                    st.toast(f"Request for {req['Full_Name']} rejected.", icon="❌")
                                    try:
                                        sheets_manager.log_user_activity(
                                            action="Rejected",
                                            username=str(req.get("Username", "")),
                                            full_name=str(req.get("Full_Name", "")),
                                            role=str(req.get("Role", "")),
                                            performed_by=username,
                                        )
                                    except Exception:
                                        pass
                                    try:
                                        notify_user_request_status(
                                            to_email=str(req.get("Email", "")),
                                            full_name=str(req.get("Full_Name", "")),
                                            username=str(req.get("Username", "")),
                                            status="Rejected",
                                        )
                                    except Exception:
                                        pass
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"❌ {ex}")
        except Exception as ex:
            st.error(f"❌ Could not load requests: {ex}")

    with tab_all:
        try:
            all_req_df = sheets_manager.get_user_requests()
            if all_req_df.empty:
                st.info("No requests yet.")
            else:
                show = ["Request_ID","Username","Full_Name","Email","Role","Status","Requested_Date","Approved_By"]
                show = [c for c in show if c in all_req_df.columns]
                st.dataframe(all_req_df[show], use_container_width=True, hide_index=True)
        except Exception as ex:
            st.error(f"❌ {ex}")

    with tab_users:
        st.subheader("Active Users")
        st.caption("You cannot delete your own account.")
        with open("config.yaml", "r") as f:
            _cfg = yaml.safe_load(f)
        active_users = _cfg.get("users", {})

        if not active_users:
            st.info("No active users found.")
        else:
            for uname, udata in active_users.items():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                    c1.markdown(f"**{udata.get('name', '')}**  `{uname}`")
                    c2.markdown(f"Role: **{udata.get('role','').title()}**")
                    with c3:
                        st.markdown("")   # spacing
                    with c4:
                        if uname == username:
                            st.button("🔒 You", key=f"del_{uname}", disabled=True, use_container_width=True)
                        else:
                            if st.button("🗑️ Delete", key=f"del_{uname}", type="secondary", use_container_width=True):
                                st.session_state[f"confirm_del_{uname}"] = True

                    # Confirmation step
                    if st.session_state.get(f"confirm_del_{uname}"):
                        st.warning(f"⚠️ Are you sure you want to delete **{udata.get('name','')}** (`{uname}`)? This cannot be undone.")
                        conf1, conf2 = st.columns(2)
                        with conf1:
                            if st.button("✅ Yes, Delete", key=f"yes_del_{uname}", type="primary", use_container_width=True):
                                try:
                                    auth.remove_user_from_config(uname)
                                    try:
                                        sheets_manager.log_user_activity(
                                            action="Deleted",
                                            username=uname,
                                            full_name=udata.get("name", ""),
                                            role=udata.get("role", ""),
                                            performed_by=username,
                                        )
                                    except Exception:
                                        pass
                                    st.session_state.pop(f"confirm_del_{uname}", None)
                                    st.toast(f"🗑️ User '{uname}' deleted.", icon="🗑️")
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"❌ {ex}")
                        with conf2:
                            if st.button("Cancel", key=f"cancel_del_{uname}", use_container_width=True):
                                st.session_state.pop(f"confirm_del_{uname}", None)
                                st.rerun()

    with tab_log:
        st.subheader("🕓 User Activity Log")
        st.caption("Complete history of all approvals, rejections, and deletions.")
        try:
            log_df = sheets_manager.get_user_activity_log()
            if log_df.empty:
                st.info("No activity recorded yet.")
            else:
                # Friendly display
                action_icons = {"Approved": "✅", "Rejected": "❌", "Deleted": "🗑️"}
                log_df["Action"] = log_df["Action"].apply(
                    lambda a: f"{action_icons.get(a, '•')} {a}"
                )
                log_df.rename(columns={
                    "Timestamp":    "Date & Time",
                    "Full_Name":    "User",
                    "Username":     "Username",
                    "Role":         "Role",
                    "Action":       "Action",
                    "Performed_By": "Performed By",
                }, inplace=True)
                show_cols = ["Date & Time", "Action", "User", "Username", "Role", "Performed By"]
                show_cols = [c for c in show_cols if c in log_df.columns]
                st.dataframe(log_df[show_cols], use_container_width=True, hide_index=True)
        except Exception as ex:
            st.error(f"❌ Could not load activity log: {ex}")
