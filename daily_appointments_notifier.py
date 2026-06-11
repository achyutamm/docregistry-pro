"""
Standalone daily "Today's Appointments" notifier for DocRegistry Pro.

Designed to run independently of the Streamlit app (e.g., via a GitHub Actions
scheduled workflow or Windows Task Scheduler) so the notification goes out at a
fixed time every day, regardless of whether anyone has the app open.

Usage:
    python daily_appointments_notifier.py
"""

from utils.sheets_manager import SheetsManager
from utils.telegram_sender import notify_today_appointments


def main():
    sm = SheetsManager()
    df = sm.get_appointments_for_date()
    print(f"Found {len(df)} appointment(s) for today.")
    notify_today_appointments(df.to_dict("records"))
    print("Notification sent.")


if __name__ == "__main__":
    main()
