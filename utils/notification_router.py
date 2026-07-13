"""
Routes notification calls to Telegram, WhatsApp (Twilio), or both
based on notifications.provider in config.yaml.

Callers import from here — never directly from telegram_sender or
whatsapp_sender — so switching provider is a single config change.
"""
import yaml


def _provider() -> str:
    try:
        with open("config.yaml", "r") as f:
            cfg = yaml.safe_load(f)
        return str(cfg.get("notifications", {}).get("provider", "telegram")).lower()
    except Exception:
        return "telegram"


def notify_new_entry(record: dict):
    provider = _provider()
    if provider in ("telegram", "both"):
        try:
            from utils.telegram_sender import notify_new_entry as _tg
            _tg(record)
        except Exception:
            pass
    if provider in ("whatsapp", "both"):
        try:
            from utils.whatsapp_sender import notify_new_entry as _wa
            _wa(record)
        except Exception:
            pass


def notify_today_appointments(appointments: list):
    provider = _provider()
    if provider in ("telegram", "both"):
        try:
            from utils.telegram_sender import notify_today_appointments as _tg
            _tg(appointments)
        except Exception:
            pass
    if provider in ("whatsapp", "both"):
        try:
            from utils.whatsapp_sender import notify_today_appointments as _wa
            _wa(appointments)
        except Exception:
            pass
