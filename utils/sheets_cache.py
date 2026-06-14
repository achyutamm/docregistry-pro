"""
Cached SheetsManager factory + cached reads for Streamlit pages.

SheetsManager() does several Google Sheets API reads on construction
(open_by_key + worksheet lookups + header checks). Streamlit reruns the
whole script on every interaction, so creating a fresh SheetsManager each
time quickly burns through the API's "read requests per minute" quota.
st.cache_resource builds it once per app process and reuses it.

On top of that, the actual sheet data (records, history, user requests,
activity log) is cached for RECORDS_TTL / ADMIN_TTL seconds via
st.cache_data, shared across all users/sessions on the server. Any code
path that writes to a sheet must call the matching clear_*_cache() so the
writer's own change is visible immediately instead of waiting for the TTL.
"""

import streamlit as st
from utils.sheets_manager import SheetsManager

# How long cached sheet data stays fresh before a forced refetch.
RECORDS_TTL = 30  # Entry_ID rows + Edit_History
ADMIN_TTL = 30    # User_Requests + User_Activity_Log


@st.cache_resource(show_spinner=False)
def get_sheets_manager() -> SheetsManager:
    return SheetsManager()


# =====================================================
# REGISTRY RECORDS
# =====================================================
@st.cache_data(ttl=RECORDS_TTL, show_spinner=False)
def get_all_records_cached(_sm: SheetsManager):
    return _sm.get_all_records()


def clear_records_cache():
    get_all_records_cached.clear()


# =====================================================
# EDIT HISTORY
# =====================================================
@st.cache_data(ttl=RECORDS_TTL, show_spinner=False)
def get_history_cached(_sm: SheetsManager, entry_id=None):
    return _sm.get_history(entry_id)


def clear_history_cache():
    get_history_cached.clear()


# =====================================================
# USER REQUESTS (signup approvals)
# =====================================================
@st.cache_data(ttl=ADMIN_TTL, show_spinner=False)
def get_user_requests_cached(_sm: SheetsManager, status=None):
    return _sm.get_user_requests(status=status)


def clear_user_requests_cache():
    get_user_requests_cached.clear()


# =====================================================
# USER ACTIVITY LOG
# =====================================================
@st.cache_data(ttl=ADMIN_TTL, show_spinner=False)
def get_user_activity_log_cached(_sm: SheetsManager):
    return _sm.get_user_activity_log()


def clear_user_activity_log_cache():
    get_user_activity_log_cached.clear()
