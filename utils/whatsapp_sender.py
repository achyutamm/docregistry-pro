import os
import yaml
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def _whatsapp_config() -> dict:
    try:
        with open("config.yaml", "r") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("whatsapp", {})
    except Exception:
        return {}


def _enabled() -> bool:
    return bool(_whatsapp_config().get("enabled", False))


def _provider() -> str:
    return str(_whatsapp_config().get("provider", "twilio")).lower()


# ── Baileys (group messaging) ──────────────────────────────────────────────────

def _send_via_baileys(body: str):
    wa_cfg = _whatsapp_config()
    api_url = wa_cfg.get("baileys_api_url", "http://localhost:3001").rstrip("/")
    group_id = wa_cfg.get("group_id", "").strip()

    if not group_id:
        raise ValueError("whatsapp.group_id not set in config.yaml. Run 'npm run list-groups' in baileys_service/")

    resp = requests.post(
        f"{api_url}/send",
        json={"group_id": group_id, "message": body},
        timeout=10,
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Baileys send failed: {data.get('error', 'unknown error')}")


# ── Twilio (individual numbers) ────────────────────────────────────────────────

def _twilio_credentials():
    return (
        os.getenv("TWILIO_ACCOUNT_SID", ""),
        os.getenv("TWILIO_AUTH_TOKEN", ""),
    )


def _send_via_twilio(body: str):
    from twilio.rest import Client

    account_sid, auth_token = _twilio_credentials()
    if not account_sid or not auth_token:
        raise ValueError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set in .env")

    wa_cfg = _whatsapp_config()
    from_number = wa_cfg.get("from_number", "").strip()
    recipient_numbers = wa_cfg.get("recipient_numbers", [])

    if not from_number:
        raise ValueError("whatsapp.from_number not set in config.yaml")
    if not recipient_numbers:
        raise ValueError("whatsapp.recipient_numbers is empty in config.yaml")

    client = Client(account_sid, auth_token)
    for number in recipient_numbers:
        number = str(number).strip()
        if not number.startswith("+"):
            number = f"+{number}"
        client.messages.create(
            from_=f"whatsapp:{from_number}",
            body=body,
            to=f"whatsapp:{number}",
        )


# ── Public API ─────────────────────────────────────────────────────────────────

def send_whatsapp_message(body: str):
    if _provider() == "baileys":
        _send_via_baileys(body)
    else:
        _send_via_twilio(body)


def notify_new_entry(record: dict):
    if not _enabled():
        return

    text = (
        "📝 *New Entry — DocRegistry Pro*\n\n"
        f"*Entry ID:* {record.get('entry_id', '')}\n"
        f"*Doc Type:* {record.get('doc_type', '')}\n"
        f"*Appointment Date:* {record.get('appointment_date', '')}\n"
        f"*Appointment Time:* {record.get('appointment_time', '')}\n"
        f"*SRO:* {record.get('sro', '')}\n"
        f"*Party Name 1:* {record.get('party_name_1', '')}\n"
        f"*Party 1 Mobile:* {record.get('party1_mobile', '')}\n"
        f"*Party Name 2:* {record.get('party_name_2', '') or '—'}\n"
        f"*GARVI App ID:* {record.get('garvi_application_id', '')}\n"
        f"*Index App No:* {record.get('index_application_no', '')}\n"
        f"*Index No:* {record.get('index_no', '')}\n"
        f"*Search No:* {record.get('search_no', '')}\n"
        f"*Title Status:* {record.get('title_status', '')}\n"
        f"*Created By:* {record.get('created_by', '')}\n"
        f"*Entry Date:* {record.get('entry_date', '')}  *Time:* {record.get('entry_time', '')}"
    )

    try:
        send_whatsapp_message(text)
    except Exception:
        pass


def notify_today_appointments(appointments: list):
    if not _enabled():
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    count = len(appointments)

    if count == 0:
        try:
            send_whatsapp_message(
                f"📅 *Today's Appointments — {today_str}*\n\nNo appointments scheduled for today."
            )
        except Exception:
            pass
        return

    try:
        send_whatsapp_message(
            f"📅 *Today's Appointments — {today_str}*\n\nTotal: {count} appointment(s)"
        )
    except Exception:
        pass

    for appt in appointments:
        text = (
            f"*Entry ID:* {appt.get('Entry_ID', '')}\n"
            f"*Doc Type:* {appt.get('Doc_Type', '')}\n"
            f"*Date:* {appt.get('Appointment Date', '')}  "
            f"*Time:* {appt.get('Appointment Time', '')}\n"
            f"*SRO:* {appt.get('SRO', '')}\n"
            f"*Party 1:* {appt.get('Party_Name 1', '')}\n"
            f"*Mobile:* {appt.get('Party_Name 1 Mobile_No', '')}\n"
            f"*Party 2:* {appt.get('Party_Name 2', '') or '—'}\n"
            f"*GARVI App ID:* {appt.get('Garvi_Application_ID', '')}\n"
            f"*Index No:* {appt.get('Index_No', '')}  "
            f"*Search No:* {appt.get('Search_No', '')}\n"
            f"*Status:* {appt.get('Title_Status', '')}"
        )
        try:
            send_whatsapp_message(text)
        except Exception:
            pass
