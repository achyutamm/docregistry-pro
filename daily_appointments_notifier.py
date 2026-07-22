"""
Standalone daily appointments notifier for DocRegistry Pro.

Runs via GitHub Actions on two schedules:
  Reminder 1 — 5 PM IST (day before): python daily_appointments_notifier.py --reminder=1
  Reminder 2 — 9 AM IST (day of):     python daily_appointments_notifier.py --reminder=2

Usage:
    python daily_appointments_notifier.py --reminder=1
    python daily_appointments_notifier.py --reminder=2  (default)
"""

import sys
import time
from datetime import datetime, timedelta
from utils.sheets_manager import SheetsManager
from utils.notification_router import notify_today_appointments, notify_tomorrow_appointments

MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds between retries


def run(reminder: int):
    sm = SheetsManager()

    if reminder == 1:
        # Day-before reminder: fetch tomorrow's appointments
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        df = sm.get_appointments_for_date(tomorrow)
        print(f"Reminder 1 (day-before): found {len(df)} appointment(s) for {tomorrow}.")
        notify_tomorrow_appointments(df.to_dict("records"), tomorrow)
    else:
        # Day-of reminder: fetch today's appointments
        df = sm.get_appointments_for_date()
        print(f"Reminder 2 (day-of): found {len(df)} appointment(s) for today.")
        notify_today_appointments(df.to_dict("records"))

    print("Notification sent.")


def main():
    # Parse --reminder=1 or --reminder=2 (default 2)
    reminder = 2
    for arg in sys.argv[1:]:
        if arg.startswith("--reminder="):
            try:
                reminder = int(arg.split("=")[1])
            except ValueError:
                pass

    print(f"Running reminder {reminder}...")

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            run(reminder)
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
