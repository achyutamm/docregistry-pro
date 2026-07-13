import gspread
import pandas as pd
import yaml
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

def _load_google_config():
    """Read active credentials path and sheet ID from config.yaml."""
    try:
        with open("config.yaml", "r") as f:
            cfg = yaml.safe_load(f)
        google_cfg  = cfg.get("google", {})
        active      = google_cfg.get("active_account", "default")
        account_cfg = google_cfg.get("accounts", {}).get(active, {})
        cred_path   = account_cfg.get("credentials") or os.getenv("GOOGLE_CREDENTIALS_PATH")
        sheet_id    = account_cfg.get("sheet_id")    or os.getenv("GOOGLE_SHEET_ID")
        return cred_path, sheet_id, active
    except Exception:
        # Fallback to .env if config.yaml is unavailable
        return os.getenv("GOOGLE_CREDENTIALS_PATH"), os.getenv("GOOGLE_SHEET_ID"), "default"

class SheetsManager:

    def __init__(self):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        cred_path, sheet_id, active_account = _load_google_config()

        creds = ServiceAccountCredentials.from_json_keyfile_name(
            cred_path,
            scope
        )

        self.client         = gspread.authorize(creds)
        self.workbook       = self.client.open_by_key(sheet_id)
        self.active_account = active_account
        self.sheet    = self.workbook.sheet1

        # Get or auto-create the Edit_History audit sheet
        try:
            self.history_sheet = self.workbook.worksheet("Edit_History")
        except Exception:
            self.history_sheet = self.workbook.add_worksheet(
                title="Edit_History", rows=5000, cols=7
            )
            self.history_sheet.append_row([
                "Entry_ID", "Edited_By", "Edit_Date", "Edit_Time",
                "Field", "Old_Value", "New_Value"
            ])

        # Get or auto-create User_Requests sheet
        try:
            self.user_requests_sheet = self.workbook.worksheet("User_Requests")
        except Exception:
            self.user_requests_sheet = self.workbook.add_worksheet(
                title="User_Requests", rows=1000, cols=10
            )
            self.user_requests_sheet.append_row([
                "Request_ID", "Username", "Full_Name", "Email",
                "Role", "Password", "Status", "Requested_Date", "Approved_By",
                "Config_Access_Requested"
            ])

        # Get or auto-create User_Activity_Log sheet
        try:
            self.activity_log_sheet = self.workbook.worksheet("User_Activity_Log")
        except Exception:
            self.activity_log_sheet = self.workbook.add_worksheet(
                title="User_Activity_Log", rows=2000, cols=6
            )
            self.activity_log_sheet.append_row([
                "Timestamp", "Action", "Username", "Full_Name", "Role", "Performed_By"
            ])

        # Single source of truth for headers
        self.headers = [
            "Entry_ID",
            "Doc_Type",
            "Appointment Date",
            "Appointment Time",
            "SRO",
            "Party_Name 1",
            "Party_Name 1 Mobile_No",
            "Party_Name 2",
            "Garvi_Application_ID",
            "Inedex_Application_No",
            "Index_No",
            "Search_No",
            "Title_Status",
            "Created_By",
            "Entry_Date",
            "Entry_Time"
        ]

        # Auto-create headers in Sheet1 if it is empty (must be after self.headers is set)
        self._ensure_headers()
        self._ensure_history_headers()
        self._ensure_user_requests_headers()
        self._ensure_activity_log_headers()

    # =====================================================
    # ENSURE HEADERS (AUTO-SETUP ON EMPTY SHEET)
    # =====================================================
    def _ensure_headers(self):
        first_row = self.sheet.row_values(1)
        if not first_row:
            self.sheet.insert_row(self.headers, 1)

    def _ensure_history_headers(self):
        """Insert the header row in Edit_History if it is missing or data is in row 1."""
        first_row = self.history_sheet.row_values(1)
        if not first_row or first_row[0] != "Entry_ID":
            self.history_sheet.insert_row(
                ["Entry_ID", "Edited_By", "Edit_Date", "Edit_Time", "Field", "Old_Value", "New_Value"],
                1
            )

    def _ensure_activity_log_headers(self):
        _hdrs = ["Timestamp", "Action", "Username", "Full_Name", "Role", "Performed_By"]
        first_row = self.activity_log_sheet.row_values(1)
        if not first_row:
            self.activity_log_sheet.insert_row(_hdrs, 1)
        elif first_row[0] not in ("Timestamp", "") and not any(h == first_row[0] for h in _hdrs):
            self.activity_log_sheet.insert_row(_hdrs, 1)

    def _ensure_user_requests_headers(self):
        """Insert the header row in User_Requests only if the first row is not already the header."""
        _hdrs = self._USER_REQUEST_HEADERS
        first_row = self.user_requests_sheet.row_values(1)
        # Only insert if the sheet is empty OR the first cell is clearly a data value (not the header)
        if not first_row:
            self.user_requests_sheet.insert_row(_hdrs, 1)
        elif first_row[0] not in ("Request_ID", "") and not any(h == first_row[0] for h in _hdrs):
            self.user_requests_sheet.insert_row(_hdrs, 1)
        elif "Config_Access_Requested" not in first_row:
            # Migrate existing sheets created before this column was added
            self.user_requests_sheet.update_cell(1, len(first_row) + 1, "Config_Access_Requested")

    # =====================================================
    # FIND DUPLICATES (CASE-INSENSITIVE, AND/OR)
    # =====================================================
    def find_duplicates(self, check_values: dict, mode="AND"):
        records = self.sheet.get_all_records(expected_headers=self.headers)
        matches = []

        for row in records:
            comparisons = []
            for field, value in check_values.items():
                sheet_val = str(row.get(field, "")).strip().lower()
                input_val = str(value).strip().lower()
                comparisons.append(sheet_val == input_val)

            if mode == "AND" and all(comparisons):
                matches.append(row)
            elif mode == "OR" and any(comparisons):
                matches.append(row)

        return matches

    # =====================================================
    # ADD RECORD
    # =====================================================
    def add_record(
        self,
        doc_type,
        appointment_date,
        appointment_time,
        sro,
        party_name_1,
        party1_mobile,
        party_name_2,
        garvi_application_id,
        index_application_no,
        index_no,
        search_no,
        title_status,
        created_by,
        entry_date,
        entry_time
    ):
        entry_id = datetime.now().strftime("%Y%m%d%H%M%S")

        row = [
            entry_id,
            doc_type,
            appointment_date,
            appointment_time,
            sro,
            party_name_1,
            party1_mobile,
            party_name_2,
            garvi_application_id,
            index_application_no,
            index_no,
            search_no,
            title_status,
            created_by,
            entry_date,
            entry_time
        ]

        next_row = len(self.sheet.col_values(1)) + 1
        self.sheet.insert_row(row, next_row)

        return True, entry_id

    # =====================================================
    # UPDATE RECORD
    # =====================================================
    def update_record(self, entry_id, doc_type, appointment_date, appointment_time,
                      sro, party_name_1, party1_mobile, party_name_2,
                      garvi_application_id, index_application_no, index_no,
                      search_no, title_status):
        cell = self.sheet.find(str(entry_id), in_column=1)
        if not cell:
            return False
        row = cell.row
        # Update columns B–M only; Entry_ID, Created_By, Entry_Date/Time are preserved
        # value_input_option='RAW' prevents Google Sheets from auto-converting
        # "10:15:00" into a time fraction number, which breaks history comparison.
        self.sheet.update(
            f"B{row}:M{row}",
            [[doc_type, appointment_date, appointment_time, sro,
              party_name_1, party1_mobile, party_name_2,
              garvi_application_id, index_application_no, index_no,
              search_no, title_status]],
            value_input_option='RAW'
        )
        return True

    # =====================================================
    # LOG EDIT HISTORY
    # =====================================================
    def log_history(self, entry_id, edited_by, changes):
        """
        changes: list of (field_name, old_value, new_value)
        Appends one row per changed field to the Edit_History sheet.
        """
        edit_date = datetime.now().strftime("%Y-%m-%d")
        edit_time = datetime.now().strftime("%H:%M:%S")
        for field, old_val, new_val in changes:
            self.history_sheet.append_row([
                str(entry_id),
                str(edited_by),
                edit_date,
                edit_time,
                str(field),
                str(old_val),
                str(new_val)
            ])

    # =====================================================
    # GET EDIT HISTORY
    # =====================================================
    def get_history(self, entry_id=None):
        """Return full audit log, optionally filtered to one entry_id."""
        _cols  = ["Entry_ID","Edited_By","Edit_Date","Edit_Time","Field","Old_Value","New_Value"]
        _empty = pd.DataFrame(columns=_cols)

        # FORMATTED_VALUE (default) returns human-readable strings for every cell type:
        # text cells return as-is, date cells return "2026-05-27", time cells return "10:00:00".
        rows = self.history_sheet.get_all_values()
        if len(rows) < 2:
            return _empty

        headers = [str(h).strip() for h in rows[0]]

        try:
            df = pd.DataFrame(rows[1:], columns=headers)
        except Exception:
            return _empty

        if "Entry_ID" not in df.columns:
            return _empty

        df["Entry_ID"] = df["Entry_ID"].astype(str).str.strip().str.replace(",", "", regex=False)

        if entry_id:
            clean_id = str(entry_id).strip().replace(",", "")
            df = df[df["Entry_ID"] == clean_id]

        return df

    # =====================================================
    # USER REQUESTS
    # =====================================================
    def add_user_request(self, username, full_name, email, role, password, config_access_requested="No"):
        request_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self.user_requests_sheet.append_row([
            request_id, username, full_name, email,
            role, password, "Pending",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "",
            config_access_requested
        ])
        return request_id

    _USER_REQUEST_HEADERS = [
        "Request_ID", "Username", "Full_Name", "Email",
        "Role", "Password", "Status", "Requested_Date", "Approved_By",
        "Config_Access_Requested"
    ]

    def get_user_requests(self, status=None):
        records = self.user_requests_sheet.get_all_records(
            expected_headers=self._USER_REQUEST_HEADERS
        )
        df = pd.DataFrame(records)
        if df.empty:
            return df
        # Drop garbage rows where Request_ID is not a numeric timestamp
        # (e.g. rows that contain stale sheet headers like "Entry_ID")
        df = df[pd.to_numeric(df["Request_ID"], errors="coerce").notna()].reset_index(drop=True)
        if status:
            df = df[df["Status"] == status]
        return df

    def email_exists(self, email: str) -> bool:
        """Return True if the given email belongs to an already-approved user request."""
        if not email:
            return False
        try:
            records = self.user_requests_sheet.get_all_records(
                expected_headers=self._USER_REQUEST_HEADERS
            )
            for row in records:
                if str(row.get("Status", "")).strip() == "Approved" and \
                   str(row.get("Email", "")).strip().lower() == email.strip().lower():
                    return True
        except Exception:
            pass
        return False

    def get_user_email_from_requests(self, username: str) -> str:
        """Return the email stored in User_Requests for the given username, or '' if not found."""
        try:
            records = self.user_requests_sheet.get_all_records(
                expected_headers=self._USER_REQUEST_HEADERS
            )
            for row in records:
                if str(row.get("Username", "")).strip().lower() == username.strip().lower():
                    return str(row.get("Email", "")).strip()
        except Exception:
            pass
        return ""

    def update_request_status(self, request_id, status, approved_by=""):
        records = self.user_requests_sheet.get_all_records(
            expected_headers=self._USER_REQUEST_HEADERS
        )
        for i, row in enumerate(records, start=2):  # row 1 is header
            if str(row.get("Request_ID", "")) == str(request_id):
                self.user_requests_sheet.update_cell(i, 7, status)      # Status col
                self.user_requests_sheet.update_cell(i, 9, approved_by) # Approved_By col
                return True
        return False

    # =====================================================
    # USER ACTIVITY LOG
    # =====================================================
    _ACTIVITY_LOG_HEADERS = ["Timestamp", "Action", "Username", "Full_Name", "Role", "Performed_By"]

    def log_user_activity(self, action: str, username: str, full_name: str,
                          role: str, performed_by: str):
        """Append one row to User_Activity_Log."""
        self.activity_log_sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            action, username, full_name, role, performed_by
        ])

    def get_user_activity_log(self):
        """Return full User_Activity_Log as a DataFrame, newest first."""
        _empty = pd.DataFrame(columns=self._ACTIVITY_LOG_HEADERS)
        try:
            records = self.activity_log_sheet.get_all_records(
                expected_headers=self._ACTIVITY_LOG_HEADERS
            )
        except Exception:
            return _empty
        if not records:
            return _empty
        df = pd.DataFrame(records)
        if "Timestamp" in df.columns:
            df = df.sort_values("Timestamp", ascending=False)
        return df.reset_index(drop=True)

    # =====================================================
    # READ RECORDS
    # =====================================================
    def get_all_records(self):
        df = pd.DataFrame(
            self.sheet.get_all_records(expected_headers=self.headers)
        )
        # Keep ID/number-like columns as plain strings to prevent comma formatting
        str_cols = [
            "Entry_ID", "Garvi_Application_ID", "Inedex_Application_No",
            "Index_No", "Search_No", "Party_Name 1 Mobile_No",
            "Appointment Date", "Appointment Time",
        ]
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(",", "", regex=False)
        return df

    def get_appointments_for_date(self, date_str=None):
        """Return all records whose Appointment Date matches date_str (YYYY-MM-DD). Defaults to today."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        df = self.get_all_records()
        if "Appointment Date" not in df.columns:
            return df
        return df[df["Appointment Date"].astype(str).str.strip() == date_str].reset_index(drop=True)
