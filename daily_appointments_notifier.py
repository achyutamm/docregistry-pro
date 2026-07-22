"""
Standalone daily "Today's Appointments" notifier for DocRegistry Pro.

Designed to run independently of the Streamlit app (e.g., via a GitHub Actions
scheduled workflow or Windows Task Scheduler) so the notification goes out at a
fixed time every day, regardless of whether anyone has the app open.

Usage:
    python daily_appointments_notifier.py
"""

import time
from utils.sheets_manager import SheetsManager
from utils.notification_router import notify_today_appointments

MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds between retries


def main():
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            sm = SheetsManager()
            df = sm.get_appointments_for_date()
            print(f"Found {len(df)} appointment(s) for today.")
            notify_today_appointments(df.to_dict("records"))
            print("Notification sent.")
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
