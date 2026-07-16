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


def notify_role_changed(full_name: str, username: str, old_role: str, new_role: str, changed_by: str):
    if _whatsapp_enabled():
        try:
            from utils.whatsapp_sender import notify_role_changed as _wa
            _wa(full_name, username, old_role, new_role, changed_by)
        except Exception:
            pass


def notify_config_access_changed(full_name: str, username: str, granted: bool, changed_by: str):
    if _whatsapp_enabled():
        try:
            from utils.whatsapp_sender import notify_config_access_changed as _wa
            _wa(full_name, username, granted, changed_by)
        except Exception:
            pass


def notify_user_deleted(full_name: str, username: str, role: str, deleted_by: str):
    if _whatsapp_enabled():
        try:
            from utils.whatsapp_sender import notify_user_deleted as _wa
            _wa(full_name, username, role, deleted_by)
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


def notify_record_updated(entry_id: str, record: dict, changes: list, updated_by: str):
    if _whatsapp_enabled():
        try:
            from utils.whatsapp_sender import notify_record_updated as _wa
            _wa(entry_id, record, changes, updated_by)
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
