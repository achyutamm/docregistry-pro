"""
Pending WhatsApp messages.

When the WhatsApp (Baileys) service is down, the new-entry group message and the
Party 1 checklist are stored in a "WhatsApp_Queue" tab of the records spreadsheet
instead of being lost. flush() sends them once the service is back; it runs after
any successful send, every few minutes while the app is open (auto_flush_if_due),
and from the "Send pending now" button in Configuration → WhatsApp.

Kept in the spreadsheet (not a local file) so pending messages survive app restarts
on Streamlit Cloud.
"""

import time
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials

QUEUE_TAB = "WhatsApp_Queue"
HEADERS = ["Queued_At", "Kind", "Target", "Entry_ID", "Message", "Attempts", "Last_Error"]
KIND_GROUP, KIND_DIRECT = "group", "direct"
AUTO_FLUSH_EVERY = 300   # seconds between automatic checks per browser session

_ws = None   # cached worksheet handle


def _worksheet(create: bool = False):
    """The queue tab. Only enqueue() creates it (create=True) — reading never adds a tab
    to the spreadsheet; it returns None while nothing has ever been queued."""
    global _ws
    if _ws is not None:
        return _ws
    from utils.sheets_manager import _load_google_config
    cred_path, sheet_id, _ = _load_google_config()
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        cred_path, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    workbook = gspread.authorize(creds).open_by_key(sheet_id)
    try:
        ws = workbook.worksheet(QUEUE_TAB)
    except gspread.exceptions.WorksheetNotFound:
        if not create:
            return None
        ws = workbook.add_worksheet(title=QUEUE_TAB, rows=200, cols=len(HEADERS))
        ws.append_row(HEADERS, value_input_option="RAW")
    _ws = ws
    return ws


def enqueue(kind: str, target: str, message: str, entry_id: str = "", error: str = ""):
    """Store one message to send later. kind is "group" or "direct" (target = phone)."""
    _worksheet(create=True).append_row(
        [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), kind, str(target or ""),
         str(entry_id or ""), message, 0, str(error or "")[:300]],
        value_input_option="RAW",
    )


def pending() -> list:
    """Queued messages, oldest first, each with its sheet row number as "_row"."""
    ws = _worksheet()
    if ws is None:
        return []
    rows = ws.get_all_records(expected_headers=HEADERS, numericise_ignore=["all"])   # keep phones as text
    return [{**r, "_row": i} for i, r in enumerate(rows, start=2)]


def delete(row_numbers):
    """Remove queued messages by sheet row (bottom-up so row numbers stay valid)."""
    ws = _worksheet()
    if ws is None:
        return
    for row in sorted(set(row_numbers), reverse=True):
        ws.delete_rows(row)


def flush() -> dict:
    """Try to send every queued message. Stops early if WhatsApp is still down.
    Returns {"sent": n, "failed": n, "remaining": n, "stopped": reason-or-""}."""
    from utils import whatsapp_sender as ws_mod

    items = pending()
    sent, failed, stopped = 0, 0, ""
    ws = _worksheet()
    for item in items:
        row = item["_row"] - sent          # rows above shift up as sent items are removed
        try:
            if item["Kind"] == KIND_DIRECT:
                ws_mod.send_direct_message(item["Target"], item["Message"])
            else:
                ws_mod._send_via_baileys(
                    f"⏰ _Sent late — WhatsApp was down when this was created ({item['Queued_At']})_\n\n"
                    + item["Message"]
                )
        except ws_mod.WhatsAppUnavailable as ex:
            stopped = str(ex)             # still down — leave everything for next time
            break
        except Exception as ex:           # e.g. number not on WhatsApp: keep it visible for an admin
            failed += 1
            attempts = int(item.get("Attempts") or 0) + 1
            ws.update(f"F{row}:G{row}", [[attempts, str(ex)[:300]]], value_input_option="RAW")
            continue
        # Remove it straight away so the app and the scheduled GitHub job, if they
        # run at the same time, are very unlikely to send the same message twice.
        ws.delete_rows(row)
        sent += 1
    return {"sent": sent, "failed": failed, "remaining": len(items) - sent, "stopped": stopped}


def auto_flush_if_due():
    """Called on page load: at most every AUTO_FLUSH_EVERY seconds per session,
    send queued messages if the WhatsApp service is connected. Never raises."""
    import streamlit as st
    now = time.time()
    if now - st.session_state.get("_wa_queue_checked", 0) < AUTO_FLUSH_EVERY:
        return None
    st.session_state["_wa_queue_checked"] = now
    try:
        from utils.whatsapp_sender import baileys_connected
        if not baileys_connected():
            return None
        if not pending():
            return None
        return flush()
    except Exception:
        return None
