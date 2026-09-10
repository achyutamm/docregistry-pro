"""
Standalone pending-records alert for DocRegistry Pro.

Mirrors the Dashboard's "Pending Records Alert" panel: records currently in
Pending status, with Days Pending = today - Entry_Date. Only messages the
WhatsApp/Telegram group when at least one record has been pending for over
30 days, to avoid noise on quiet weeks.

Runs via GitHub Actions on a weekly schedule.

Usage:
    python pending_records_notifier.py
"""

import sys
import time
import pandas as pd

from utils.sheets_manager import SheetsManager
from utils.notification_router import notify_pending_records_alert

MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds between retries

PENDING_DAYS_THRESHOLD = 30


def run():
    sm = SheetsManager()
    df = sm.get_all_records()

    pending_all = df[df["Title_Status"].str.lower() == "pending"].copy()
    if pending_all.empty:
        print("No records are currently in Pending status. Nothing to send.")
        return

    pending_all["Entry_Date_dt"] = pd.to_datetime(pending_all["Entry_Date"], errors="coerce")
    today_ts = pd.Timestamp.today().normalize()
    pending_all["Days Pending"] = (today_ts - pending_all["Entry_Date_dt"]).dt.days

    long_pending = pending_all.sort_values("Days Pending", ascending=False)
    over_30 = long_pending[long_pending["Days Pending"] > PENDING_DAYS_THRESHOLD]

    print(f"{len(over_30)} record(s) pending for over {PENDING_DAYS_THRESHOLD} days "
          f"— {len(long_pending)} pending total.")

    if over_30.empty:
        print("Nothing over the threshold — no alert sent.")
        return

    notify_pending_records_alert(
        over_30.to_dict("records"),
        len(over_30),
        len(long_pending),
    )
    print("Alert sent.")


def main():
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            run()
            return
        except Exception as e:
            last_error = e
            print(f"Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)

    print(f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
