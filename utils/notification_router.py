"""
Routes notification calls to Telegram, WhatsApp, or both
based on telegram.enabled and whatsapp.enabled in config.yaml.

Switch providers by toggling enabled: true/false in config.yaml — no code changes needed.
"""
import yaml


def _cfg() -> dict:
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def _telegram_enabled() -> bool:
    return bool(_cfg().get("telegram", {}).get("enabled", False))


def _whatsapp_enabled() -> bool:
    return bool(_cfg().get("whatsapp", {}).get("enabled", False))


def notify_new_entry(record: dict):
    if _telegram_enabled():
        try:
            from utils.telegram_sender import notify_new_entry as _tg
            _tg(record)
        except Exception:
            pass
    if _whatsapp_enabled():
        try:
            from utils.whatsapp_sender import notify_new_entry as _wa
            _wa(record)
        except Exception:
            pass


def notify_user_requested(full_name: str, username: str, role: str):
    if _telegram_enabled():
        try:
            from utils.telegram_sender import notify_user_requested as _tg
            _tg(full_name, username, role)
        except Exception:
            pass
    if _whatsapp_enabled():
        try:
            from utils.whatsapp_sender import notify_user_requested as _wa
            _wa(full_name, username, role)
        except Exception:
            pass


def notify_user_rejected(full_name: str, username: str, role: str):
    if _telegram_enabled():
        try:
            from utils.telegram_sender import notify_user_rejected as _tg
            _tg(full_name, username, role)
        except Exception:
            pass
    if _whatsapp_enabled():
        try:
            from utils.whatsapp_sender import notify_user_rejected as _wa
            _wa(full_name, username, role)
        except Exception:
            pass


def notify_user_approved(full_name: str, username: str, role: str):
    if _telegram_enabled():
        try:
            from utils.telegram_sender import notify_user_approved as _tg
            _tg(full_name, username, role)
        except Exception:
            pass
    if _whatsapp_enabled():
        try:
            from utils.whatsapp_sender import notify_user_approved as _wa
            _wa(full_name, username, role)
        except Exception:
            pass


def notify_today_appointments(appointments: list):
    if _telegram_enabled():
        try:
            from utils.telegram_sender import notify_today_appointments as _tg
            _tg(appointments)
        except Exception:
            pass
    if _whatsapp_enabled():
        try:
            from utils.whatsapp_sender import notify_today_appointments as _wa
            _wa(appointments)
        except Exception:
            pass
