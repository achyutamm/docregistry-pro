"""
Standalone pending-records alert for DocRegistry Pro.

Mirrors the Dashboard's "Pending Records Alert" panel: records currently in
Pending status, with Days Pending = today - Entry_Date. Only messages the
WhatsApp/Telegram group when at least one record has been pending for over
30 days, to avoid noise on quiet weeks.

With --tentative it reminds the group instead about records still in the
Tentative Records tab more than 15 days after they were entered.

Runs via GitHub Actions: weekly for pending records, on the 1st and 16th of
each month for tentative records.

Usage:
    python pending_records_notifier.py
    python pending_records_notifier.py --tentative
"""

import sys
import time
import pandas as pd

from utils.sheets_manager import SheetsManager, with_days_tentative, TENTATIVE_ALERT_DAYS
from utils.notification_router import notify_pending_records_alert, notify_tentative_overdue
from utils.gujarati_translit import use_english_names

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
        [use_english_names(r) for r in over_30.to_dict("records")],
        len(over_30),
        len(long_pending),
    )
    print("Alert sent.")


def run_tentative():
    df = SheetsManager().get_tentative_records()
    if df.empty:
        print("No tentative records. Nothing to send.")
        return

    df = with_days_tentative(df)
    overdue = df[df["Days Tentative"] > TENTATIVE_ALERT_DAYS]
    print(f"{len(overdue)} record(s) tentative for over {TENTATIVE_ALERT_DAYS} days "
          f"— {len(df)} tentative total.")
    if overdue.empty:
        print("Nothing over the limit — no reminder sent.")
        return

    notify_tentative_overdue([use_english_names(r) for r in overdue.to_dict("records")], len(df))
    print("Reminder sent.")


def main():
    job = run_tentative if "--tentative" in sys.argv[1:] else run
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            job()
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
