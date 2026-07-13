"""
Safe read/modify/write helpers for config.yaml's editable lookup lists.

Used by the admin-only "Configuration" section in app.py so non-technical
users can manage document types, party names, SRO offices, admin emails,
and the Telegram toggle without hand-editing YAML.
"""
import yaml

CONFIG_FILE = "config.yaml"


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)


def _get_node(cfg, path):
    node = cfg
    for key in path[:-1]:
        node = node.setdefault(key, {})
    return node


def add_list_item(path, value):
    value = value.strip()
    if not value:
        raise ValueError("Value cannot be empty.")

    cfg = load_config()
    node = _get_node(cfg, path)
    items = node.setdefault(path[-1], [])

    if any(value.lower() == str(item).lower() for item in items):
        raise ValueError(f"'{value}' already exists.")

    items.append(value)
    save_config(cfg)


def remove_list_item(path, value):
    cfg = load_config()
    node = _get_node(cfg, path)
    items = node.get(path[-1], [])

    if value not in items:
        raise ValueError(f"'{value}' not found.")

    items.remove(value)
    save_config(cfg)


def add_sro_district(name):
    name = name.strip()
    if not name:
        raise ValueError("District name cannot be empty.")

    cfg = load_config()
    sro_options = cfg.setdefault("sro_options", {})

    if any(name.lower() == str(d).lower() for d in sro_options):
        raise ValueError(f"District '{name}' already exists.")

    sro_options[name] = []
    save_config(cfg)


def remove_sro_district(name):
    cfg = load_config()
    sro_options = cfg.get("sro_options", {})

    if name not in sro_options:
        raise ValueError(f"District '{name}' not found.")
    if sro_options[name]:
        raise ValueError(f"Remove all SRO offices from '{name}' before deleting the district.")

    del sro_options[name]
    save_config(cfg)


def set_telegram_enabled(value: bool):
    cfg = load_config()
    cfg.setdefault("telegram", {})["enabled"] = bool(value)
    save_config(cfg)


def set_whatsapp_enabled(value: bool):
    cfg = load_config()
    cfg.setdefault("whatsapp", {})["enabled"] = bool(value)
    save_config(cfg)


def set_notifications_provider(provider: str):
    allowed = ("telegram", "whatsapp", "both")
    if provider not in allowed:
        raise ValueError(f"Provider must be one of: {', '.join(allowed)}")
    cfg = load_config()
    cfg.setdefault("notifications", {})["provider"] = provider
    save_config(cfg)


def add_whatsapp_recipient(number: str):
    number = number.strip().lstrip("+")
    if not number.isdigit():
        raise ValueError("Phone number must contain digits only (no +, spaces, or dashes).")
    full = f"+{number}"
    cfg = load_config()
    recipients = cfg.setdefault("whatsapp", {}).setdefault("recipient_numbers", [])
    if full in recipients or number in recipients:
        raise ValueError(f"'{full}' is already in the recipient list.")
    recipients.append(full)
    save_config(cfg)


def remove_whatsapp_recipient(number: str):
    cfg = load_config()
    recipients = cfg.get("whatsapp", {}).get("recipient_numbers", [])
    if number not in recipients:
        raise ValueError(f"'{number}' not found in recipient list.")
    recipients.remove(number)
    save_config(cfg)


def set_whatsapp_from_number(number: str):
    number = number.strip()
    if not number:
        raise ValueError("From number cannot be empty.")
    cfg = load_config()
    cfg.setdefault("whatsapp", {})["from_number"] = number
    save_config(cfg)


def set_whatsapp_mode(mode: str):
    if mode not in ("sandbox", "production"):
        raise ValueError("Mode must be 'sandbox' or 'production'.")
    cfg = load_config()
    cfg.setdefault("whatsapp", {})["mode"] = mode
    save_config(cfg)
