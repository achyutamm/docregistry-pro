import os
import requests
import yaml
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

_DAILY_MARKER_FILE = os.path.join("data", ".last_appointment_notify.txt")


def _telegram_config():
    return (
        os.getenv("TELEGRAM_BOT_TOKEN", ""),
        os.getenv("TELEGRAM_CHAT_ID", ""),
    )


def _enabled() -> bool:
    try:
        with open("config.yaml", "r") as f:
            cfg = yaml.safe_load(f)
        return bool(cfg.get("telegram", {}).get("enabled", True))
    except Exception:
        return True


def send_telegram_message(text: str):
    """Send a message to the configured Telegram group. Raises if not configured or sending fails."""
    bot_token, chat_id = _telegram_config()
    if not bot_token or not chat_id:
        raise ValueError("Telegram not configured. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")


def notify_new_entry(record: dict):
    """Notify the Telegram group when a new register entry is added. Silently does nothing if not configured."""
    if not _enabled():
        return

    bot_token, chat_id = _telegram_config()
    if not bot_token or not chat_id:
        return

    text = (
        "📝 <b>New Entry Added — DocRegistry Pro</b>\n\n"
        f"<b>Entry ID:</b> {record.get('entry_id', '')}\n"
        f"<b>Doc Type:</b> {record.get('doc_type', '')}\n"
        f"<b>Appointment Date:</b> {record.get('appointment_date', '')}\n"
        f"<b>Appointment Time:</b> {record.get('appointment_time', '')}\n"
        f"<b>SRO:</b> {record.get('sro', '')}\n"
        f"<b>Party Name 1:</b> {record.get('party_name_1', '')}\n"
        f"<b>Party 1 Mobile No:</b> {record.get('party1_mobile', '')}\n"
        f"<b>Party Name 2:</b> {record.get('party_name_2', '') or '—'}\n"
        f"<b>GARVI Application ID:</b> {record.get('garvi_application_id', '')}\n"
        f"<b>Index Application No:</b> {record.get('index_application_no', '')}\n"
        f"<b>Index No:</b> {record.get('index_no', '')}\n"
        f"<b>Search No:</b> {record.get('search_no', '')}\n"
        f"<b>Title Status:</b> {record.get('title_status', '')}\n"
        f"<b>Created By:</b> {record.get('created_by', '')}\n"
        f"<b>Entry Date:</b> {record.get('entry_date', '')}\n"
        f"<b>Entry Time:</b> {record.get('entry_time', '')}"
    )

    try:
        send_telegram_message(text)
    except Exception:
        pass


def should_send_daily_appointments() -> bool:
    """True if today's appointments notification has not been sent yet today."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(_DAILY_MARKER_FILE, "r") as f:
            return f.read().strip() != today_str
    except Exception:
        return True


def mark_daily_appointments_sent():
    """Record that today's appointments notification has been sent."""
    try:
        os.makedirs(os.path.dirname(_DAILY_MARKER_FILE), exist_ok=True)
        with open(_DAILY_MARKER_FILE, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d"))
    except Exception:
        pass


def notify_today_appointments(appointments: list):
    """Send 'Today's Appointments' to the Telegram group — one summary message
    plus one detail message per appointment. Silently does nothing if not configured."""
    if not _enabled():
        return

    bot_token, chat_id = _telegram_config()
    if not bot_token or not chat_id:
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    count = len(appointments)

    if count == 0:
        try:
            send_telegram_message(
                f"📅 <b>Today's Appointments — {today_str}</b>\n\nNo appointments scheduled for today."
            )
        except Exception:
            pass
        return

    try:
        send_telegram_message(
            f"📅 <b>Today's Appointments — {today_str}</b>\n\nTotal: {count} appointment(s)"
        )
    except Exception:
        pass

    for appt in appointments:
        text = (
            f"<b>Entry ID:</b> {appt.get('Entry_ID', '')}\n"
            f"<b>Doc Type:</b> {appt.get('Doc_Type', '')}\n"
            f"<b>Appointment Time:</b> {appt.get('Appointment Time', '')}\n"
            f"<b>SRO:</b> {appt.get('SRO', '')}\n"
            f"<b>Party Name 1:</b> {appt.get('Party_Name 1', '')}\n"
            f"<b>Party 1 Mobile No:</b> {appt.get('Party_Name 1 Mobile_No', '')}\n"
            f"<b>Party Name 2:</b> {appt.get('Party_Name 2', '') or '—'}\n"
            f"<b>Title Status:</b> {appt.get('Title_Status', '')}\n"
            f"<b>Created By:</b> {appt.get('Created_By', '')}"
        )
        try:
            send_telegram_message(text)
        except Exception:
            pass
