import os
import re
import yaml
import requests
from datetime import datetime
from dotenv import load_dotenv

from utils import phone_utils

load_dotenv()


def _full_config() -> dict:
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _whatsapp_config() -> dict:
    return _full_config().get("whatsapp", {})


def _enabled() -> bool:
    return bool(_whatsapp_config().get("enabled", False))


def _provider() -> str:
    return str(_whatsapp_config().get("provider", "twilio")).lower()


# ── Baileys (group + direct messaging) ─────────────────────────────────────────

class WhatsAppUnavailable(RuntimeError):
    """The WhatsApp service is down or not linked — the message can be retried later."""


class NotOnWhatsApp(RuntimeError):
    """The number is not registered on WhatsApp — retrying will not help."""


def _baileys_url() -> str:
    return _whatsapp_config().get("baileys_api_url", "http://localhost:3001").rstrip("/")


def baileys_connected(timeout: float = 4) -> bool:
    """True when the Baileys service answers /status and WhatsApp is linked."""
    try:
        return bool(requests.get(f"{_baileys_url()}/status", timeout=timeout).json().get("connected"))
    except Exception:
        return False


def _post_baileys(path: str, payload: dict):
    """POST to the Baileys service, turning failures into WhatsAppUnavailable /
    NotOnWhatsApp so callers can decide whether to queue the message."""
    api_key = os.getenv("BAILEYS_API_KEY", "")
    headers = {"x-api-key": api_key} if api_key else {}
    try:
        resp = requests.post(f"{_baileys_url()}{path}", json=payload, headers=headers, timeout=15)
    except requests.exceptions.RequestException as ex:
        raise WhatsAppUnavailable(f"WhatsApp service not reachable ({type(ex).__name__})") from ex
    try:
        data = resp.json()
    except ValueError:
        raise WhatsAppUnavailable(f"WhatsApp service returned HTTP {resp.status_code}")
    if data.get("success"):
        return
    error = data.get("error", "unknown error")
    if resp.status_code == 404 and "not on whatsapp" in str(error).lower():
        raise NotOnWhatsApp(error)
    if resp.status_code >= 500:            # 503 = WhatsApp not linked, 500 = send error
        raise WhatsAppUnavailable(error)
    raise RuntimeError(f"Baileys send failed: {error}")


def _send_via_baileys(body: str):
    group_id = _whatsapp_config().get("group_id", "").strip()
    if not group_id:
        raise ValueError("whatsapp.group_id not set in config.yaml")
    _post_baileys("/send", {"group_id": group_id, "message": body})


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


def _normalize_indian_number(phone: str) -> str:
    """10-digit mobile -> 91XXXXXXXXXX (digits only, no +).
    A number that already has a country code ("+1 4155551234") keeps it."""
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if str(phone).strip().startswith("+"):
        return digits
    if len(digits) == 10:
        digits = f"91{digits}"
    return digits


def send_direct_message(phone: str, body: str):
    """Send a WhatsApp message to one individual number (not the group)."""
    number = _normalize_indian_number(phone)
    if len(number) < 8:   # country code + at least 6 digits
        raise ValueError(f"Invalid mobile number: '{phone}'")

    if _provider() == "baileys":
        _post_baileys("/send-direct", {"phone": number, "message": body})
    else:
        from twilio.rest import Client

        account_sid, auth_token = _twilio_credentials()
        if not account_sid or not auth_token:
            raise ValueError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set in .env")
        from_number = _whatsapp_config().get("from_number", "").strip()
        if not from_number:
            raise ValueError("whatsapp.from_number not set in config.yaml")
        Client(account_sid, auth_token).messages.create(
            from_=f"whatsapp:{from_number}",
            body=body,
            to=f"whatsapp:+{number}",
        )


class _KeepMissing(dict):
    """Leaves unknown {placeholders} as-is instead of raising KeyError."""
    def __missing__(self, key):
        return "{" + key + "}"


def _format_appt_time(value: str) -> str:
    """'14:30:00' -> '02:30 PM'; anything unparseable is returned unchanged."""
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(str(value).strip(), fmt).strftime("%I:%M %p")
        except ValueError:
            continue
    return str(value)


def party1_checklist_items(checklist_cfg: dict, doc_type: str) -> list:
    """Documents to ask Party 1 for: the Document Type's own list, or
    default_items when that type isn't mapped."""
    items_by_type = checklist_cfg.get("items", {}) or {}
    doc_type = str(doc_type).strip().lower()
    # Case-insensitive match so "SALE DEED" / "Sale Deed" both work
    items = next(
        (lst for name, lst in items_by_type.items() if str(name).strip().lower() == doc_type),
        checklist_cfg.get("default_items", []),
    )
    return [str(i).strip() for i in (items or []) if str(i).strip()]


def render_party1_checklist(checklist_cfg: dict, record: dict, company: str = "", contact_numbers=None):
    """Fill the message template for this record, or None when the
    Document Type has no documents to ask for."""
    items = party1_checklist_items(checklist_cfg, record.get("doc_type", ""))
    template = str(checklist_cfg.get("message", "") or "").strip()
    if not items or not template:
        return None

    contacts = " / ".join(str(n).strip() for n in (contact_numbers or []) if str(n).strip())
    if not contacts:
        # No office numbers configured: drop the "reach out to {contact_numbers}" line entirely
        template = "\n".join(l for l in template.splitlines() if "{contact_numbers}" not in l)

    values = _KeepMissing({k: ("" if v is None else str(v)) for k, v in record.items()})
    values["appointment_time"] = _format_appt_time(record.get("appointment_time", ""))
    values["party_name_2"] = record.get("party_name_2") or "—"
    values["checklist"] = "\n".join(f"{n}. {item}" for n, item in enumerate(items, 1))
    # {partners} is a whole block (heading + names) when Party 1 has partners,
    # and empty otherwise — so the template needs no extra blank-line handling.
    partners = str(record.get("party1_partners", "") or "").strip()
    heading = str(checklist_cfg.get("partners_heading", "") or "").strip().rstrip(":").strip() or "Partners"
    values["partners"] = f"\n*{heading}:*\n{partners}\n" if partners else ""
    values["contact_numbers"] = contacts
    values.setdefault("company", company)
    # Optional blocks ({partners}, a dropped contact line) can leave extra blank lines
    return re.sub(r"\n{3,}", "\n\n", template.format_map(values)).strip()


def build_party1_checklist_message(record: dict):
    cfg = _full_config()
    return render_party1_checklist(
        cfg.get("party1_checklist", {}) or {}, record, cfg.get("app", {}).get("company", ""),
        (cfg.get("whatsapp", {}) or {}).get("contact_numbers", []),
    )


def send_party1_checklist(record: dict):
    """Send the Document Type checklist to Party 1's mobile.

    Returns (status, detail) where status is one of:
      "sent", "queued" (WhatsApp down — will be sent later), "not_on_whatsapp",
      "skipped" (nothing to send / feature off), "failed".
    """
    cfg = _full_config()
    if not cfg.get("whatsapp", {}).get("enabled", False):
        return "skipped", "WhatsApp is disabled in Configuration."
    if not cfg.get("party1_checklist", {}).get("enabled", False):
        return "skipped", "Party 1 checklist messages are turned off."

    p1_cfg = cfg.get("party1_checklist", {}) or {}
    mobile = str(record.get("party1_mobile", "")).strip()
    test_mobile = phone_utils.join(p1_cfg.get("test_country_code"), p1_cfg.get("test_mobile"))
    test_mode = bool(p1_cfg.get("test_mode", False))
    if test_mode and not test_mobile:
        # Never fall back to the real party while test mode is on
        return "skipped", "Test mode is on but no test mobile number is set in Doc Checklist."

    if not mobile and not test_mode:
        return "skipped", "No Party 1 mobile number entered."

    body = build_party1_checklist_message(record)
    if body is None:
        return "skipped", f"No documents configured for '{record.get('doc_type', '')}' in Doc Checklist."

    if test_mode:
        # Test mode: never message the real party — send to the configured test number,
        # with a header saying who it would have gone to.
        body = f"🧪 *TEST* — would go to Party 1: {mobile or 'no number entered'}\n\n{body}"
        target, prefix = test_mobile, "🧪 TEST MODE — "
        sent_note = f"checklist sent to test number {test_mobile} (not to Party 1 {mobile or '— no number'})."
    else:
        target, prefix = mobile, ""
        sent_note = f"Checklist sent on WhatsApp to Party 1 ({mobile})."

    try:
        send_direct_message(target, body)
        return "sent", prefix + sent_note
    except WhatsAppUnavailable as ex:
        # Service down / not linked: keep the message and send it when WhatsApp is back
        try:
            from utils import whatsapp_queue
            whatsapp_queue.enqueue(whatsapp_queue.KIND_DIRECT, target, body, record.get("entry_id", ""), str(ex))
        except Exception as q_ex:
            return "failed", f"{prefix}WhatsApp is down ({ex}) and the checklist could not be queued: {q_ex}"
        return "queued", (f"{prefix}WhatsApp is not reachable right now — the checklist to {target} is saved as "
                          "pending and will be sent automatically when WhatsApp is back.")
    except NotOnWhatsApp:
        return "not_on_whatsapp", (f"{prefix}{target} is not on WhatsApp — the checklist was NOT sent. "
                                   "Please check the number in Edit Records, or inform Party 1 by phone.")
    except Exception as ex:
        return "failed", f"{prefix}Could not send WhatsApp to {target}: {ex}"


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
        + (f"*Party 1 Partners:*\n{str(record.get('party1_partners')).strip()}\n"
           if str(record.get('party1_partners', '') or '').strip() else "")
        + f"*Party Name 2:* {record.get('party_name_2', '') or '—'}\n"
        f"*GARVI App ID:* {record.get('garvi_application_id', '')}\n"
        f"*Index App No:* {record.get('index_application_no', '')}\n"
        f"*Index No:* {record.get('index_no', '')}\n"
        f"*Search No:* {record.get('search_no', '')}\n"
        f"*Title Status:* {record.get('title_status', '')}\n"
        f"*Remark:* {record.get('remark', '') or '—'}\n"
        f"*Created By:* {record.get('created_by', '')}\n"
        f"*Entry Date:* {record.get('entry_date', '')}  *Time:* {record.get('entry_time', '')}"
    )

    try:
        send_whatsapp_message(text)
    except WhatsAppUnavailable as ex:
        # Keep the group announcement and send it when WhatsApp is back
        try:
            from utils import whatsapp_queue
            whatsapp_queue.enqueue(whatsapp_queue.KIND_GROUP, "", text, record.get("entry_id", ""), str(ex))
        except Exception:
            pass
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


def notify_tomorrow_appointments(appointments: list, tomorrow_str: str):
    if not _enabled():
        return

    count = len(appointments)

    if count == 0:
        try:
            send_whatsapp_message(
                f"⏰ *Tomorrow's Appointment Reminder — {tomorrow_str}*\n\nNo appointments scheduled for tomorrow."
            )
        except Exception:
            pass
        return

    try:
        send_whatsapp_message(
            f"⏰ *Tomorrow's Appointment Reminder — {tomorrow_str}*\n\nTotal: {count} appointment(s) scheduled for tomorrow."
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


def notify_role_changed(full_name: str, username: str, old_role: str, new_role: str, changed_by: str):
    if not _enabled():
        return
    body = (
        f"🔄 *User Role Updated — DocRegistry Pro*\n\n"
        f"*Name:* {full_name}\n"
        f"*Username:* {username}\n"
        f"*Role Changed:* {old_role.capitalize()} → {new_role.capitalize()}\n"
        f"*Changed By:* {changed_by}"
    )
    try:
        send_whatsapp_message(body)
    except Exception:
        pass


def notify_config_access_changed(full_name: str, username: str, granted: bool, changed_by: str):
    if not _enabled():
        return
    action = "granted to" if granted else "revoked from"
    icon = "✅" if granted else "🚫"
    body = (
        f"{icon} *Config Access {('Granted' if granted else 'Revoked')} — DocRegistry Pro*\n\n"
        f"*Name:* {full_name}\n"
        f"*Username:* {username}\n"
        f"*Configuration Tab Access:* {'Granted ✅' if granted else 'Revoked 🚫'}\n"
        f"*Changed By:* {changed_by}"
    )
    try:
        send_whatsapp_message(body)
    except Exception:
        pass


def notify_user_deleted(full_name: str, username: str, role: str, deleted_by: str):
    if not _enabled():
        return
    body = (
        f"🗑️ *User Deleted — DocRegistry Pro*\n\n"
        f"*Name:* {full_name}\n"
        f"*Username:* {username}\n"
        f"*Role:* {role.capitalize()}\n"
        f"*Deleted By:* {deleted_by}"
    )
    try:
        send_whatsapp_message(body)
    except Exception:
        pass


def notify_user_requested(full_name: str, username: str, role: str):
    if not _enabled():
        return
    body = (
        f"🔔 *New Access Request — DocRegistry Pro*\n\n"
        f"*Name:* {full_name}\n"
        f"*Username:* {username}\n"
        f"*Role Requested:* {role.capitalize()}\n\n"
        f"Admin, please review and take necessary action."
    )
    try:
        send_whatsapp_message(body)
    except Exception:
        pass


def notify_user_rejected(full_name: str, username: str, role: str):
    if not _enabled():
        return
    body = (
        f"❌ *Access Request Rejected — DocRegistry Pro*\n\n"
        f"*Name:* {full_name}\n"
        f"*Username:* {username}\n"
        f"*Role:* {role.capitalize()}\n\n"
        f"This user's request has been rejected by the admin."
    )
    try:
        send_whatsapp_message(body)
    except Exception:
        pass


def notify_user_approved(full_name: str, username: str, role: str):
    if not _enabled():
        return
    role_label = role.capitalize()
    body = (
        f"✅ *New User Approved*\n\n"
        f"*Name:* {full_name}\n"
        f"*Username:* {username}\n"
        f"*Role:* {role_label}\n\n"
        f"This user has been granted access to DocRegistry Pro."
    )
    try:
        send_whatsapp_message(body)
    except Exception:
        pass


# Field display names for the edit notification
_FIELD_LABELS = {
    "Doc_Type":               "Document Type",
    "Appointment Date":       "Appointment Date",
    "Appointment Time":       "Appointment Time",
    "SRO":                    "SRO",
    "Party_Name 1":           "Party Name 1",
    "Party_Name 1 Mobile_No": "Party 1 Mobile",
    "Party_Name 2":           "Party Name 2",
    "Garvi_Application_ID":   "GARVI App ID",
    "Inedex_Application_No":  "Index App No",
    "Index_No":               "Index No",
    "Search_No":              "Search No",
    "Title_Status":           "Title Status",
    "Remark":                 "Remark",
}


def notify_pending_records_alert(over_30_records: list, over_30_count: int, total_pending: int):
    """Alert the WhatsApp group about records that have been Pending for over 30
    days — one summary message plus one detail message per overdue record.
    Silently does nothing if not configured."""
    if not _enabled():
        return

    summary = (
        "⚠️ *Pending Records Alert — DocRegistry Pro*\n\n"
        f"{over_30_count} record(s) pending for over 30 days — {total_pending} pending total.\n\n"
        f"For all {total_pending} pending records, please open DocRegistry Pro → Dashboard.\n\n"
        "Please review the overdue ones below at the earliest 🙏"
    )
    try:
        send_whatsapp_message(summary)
    except Exception:
        pass

    for rec in over_30_records:
        text = (
            f"*Entry ID:* {rec.get('Entry_ID', '')}\n"
            f"*Doc Type:* {rec.get('Doc_Type', '')}\n"
            f"*Party 1:* {rec.get('Party_Name 1', '')}\n"
            f"*Mobile:* {rec.get('Party_Name 1 Mobile_No', '')}\n"
            f"*Party 2:* {rec.get('Party_Name 2', '') or '—'}\n"
            f"*SRO:* {rec.get('SRO', '')}\n"
            f"*Appointment Date:* {rec.get('Appointment Date', '')}\n"
            f"*Entry Date:* {rec.get('Entry_Date', '')}\n"
            f"*Days Pending:* {rec.get('Days Pending', '')}\n"
            f"*Remark:* {rec.get('Remark', '') or '—'}"
        )
        try:
            send_whatsapp_message(text)
        except Exception:
            pass


def notify_record_updated(entry_id: str, record: dict, changes: list, updated_by: str):
    """
    Send a WhatsApp notification when a record is edited.

    record   — dict of all field values AFTER the save
    changes  — list of (field_key, old_value, new_value) tuples
    """
    if not _enabled():
        return
    if not changes:
        return

    # Build the changed-fields section
    change_lines = []
    for field, old, new in changes:
        label = _FIELD_LABELS.get(field, field)
        change_lines.append(f"  • *{label}:* {old or '—'} → {new or '—'}")
    changes_text = "\n".join(change_lines)

    # Full record snapshot
    body = (
        f"✏️ *Record Updated — DocRegistry Pro*\n\n"
        f"*Updated By:* {updated_by}\n"
        f"*Entry ID:* {entry_id}\n\n"
        f"*Changes ({len(changes)} field(s)):*\n"
        f"{changes_text}\n\n"
        f"━━━━━━━━━━━━ Record Details ━━━━━━━━━━━━\n"
        f"*Doc Type:* {record.get('Doc_Type', '')}\n"
        f"*Date:* {record.get('Appointment Date', '')}  "
        f"*Time:* {record.get('Appointment Time', '')}\n"
        f"*SRO:* {record.get('SRO', '')}\n"
        f"*Party 1:* {record.get('Party_Name 1', '')}\n"
        f"*Mobile:* {record.get('Party_Name 1 Mobile_No', '')}\n"
        f"*Party 2:* {record.get('Party_Name 2', '') or '—'}\n"
        f"*GARVI App ID:* {record.get('Garvi_Application_ID', '')}\n"
        f"*Index App No:* {record.get('Inedex_Application_No', '')}\n"
        f"*Index No:* {record.get('Index_No', '')}  "
        f"*Search No:* {record.get('Search_No', '')}\n"
        f"*Title Status:* {record.get('Title_Status', '')}\n"
        f"*Remark:* {record.get('Remark', '') or '—'}"
    )
    try:
        send_whatsapp_message(body)
    except Exception:
        pass
