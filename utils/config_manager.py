"""
Safe read/modify/write helpers for config.yaml's editable lookup lists.

Used by the admin-only "Configuration" section in app.py so non-technical
users can manage document types, party names, SRO offices, admin emails,
and the Telegram toggle without hand-editing YAML.
"""
import re
import yaml

CONFIG_FILE = "config.yaml"


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


class _ConfigDumper(yaml.SafeDumper):
    pass


def _str_representer(dumper, data):
    # Multi-line text (e.g. WhatsApp message templates) stays readable as a | block
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_ConfigDumper.add_representer(str, _str_representer)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(cfg, f, Dumper=_ConfigDumper, default_flow_style=False, allow_unicode=True)


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


def set_party1_checklist_enabled(value: bool):
    cfg = load_config()
    cfg.setdefault("party1_checklist", {})["enabled"] = bool(value)
    save_config(cfg)


def set_whatsapp_contact_numbers(numbers):
    """Office numbers printed in messages ({contact_numbers}), in the given order."""
    cleaned = []
    for raw in numbers or []:
        n = " ".join(str(raw or "").split())
        if not n:
            continue
        digits = "".join(ch for ch in n if ch.isdigit())
        if not re.fullmatch(r"\+?[\d ]+", n) or not 6 <= len(digits) <= 15:
            raise ValueError(f"'{n}' is not a valid phone number (digits, optional + and spaces).")
        if n not in cleaned:
            cleaned.append(n)
    cfg = load_config()
    cfg.setdefault("whatsapp", {})["contact_numbers"] = cleaned
    save_config(cfg)


def set_party1_checklist_test_mode(enabled: bool, test_mobile: str, country_code: str = "+91"):
    """Test mode sends every checklist to the test number instead of Party 1's own number."""
    from utils import phone_utils
    test_mobile = str(test_mobile or "").strip()
    if enabled and not test_mobile:
        raise ValueError("Enter a test mobile number to turn test mode on.")
    error = phone_utils.validate(country_code, test_mobile)
    if error:
        raise ValueError(error)
    cfg = load_config()
    p1 = cfg.setdefault("party1_checklist", {})
    p1["test_mode"] = bool(enabled)
    p1["test_country_code"] = phone_utils.clean_code(country_code)
    p1["test_mobile"] = test_mobile
    save_config(cfg)


def set_party1_checklist_message(message: str, partners_heading: str = None):
    """Message template shared by every document type; {checklist} becomes the numbered list.
    partners_heading is the bold title {partners} puts above the partner names."""
    # Trailing spaces per line block YAML's | style, so strip them
    message = "\n".join(line.rstrip() for line in message.strip().splitlines())
    if not message:
        raise ValueError("Message cannot be empty.")
    if "{checklist}" not in message:
        raise ValueError("Message must contain {checklist} - that is where the document list goes.")
    cfg = load_config()
    cfg.setdefault("party1_checklist", {})["message"] = message
    if partners_heading is not None:
        cfg["party1_checklist"]["partners_heading"] = str(partners_heading).strip().rstrip(":").strip() or "Partners"
    save_config(cfg)


def set_party1_checklist_items(doc_type, items):
    """Set the documents to ask for one document type.

    doc_type=None sets default_items (used by every type that isn't mapped).
    items=None removes the type's own list so it falls back to default_items;
    an empty list means nothing is sent for that type.
    """
    cfg = load_config()
    checklist = cfg.setdefault("party1_checklist", {})
    if items is not None:
        items = [str(i).strip() for i in items if str(i or "").strip()]

    if doc_type is None:
        checklist["default_items"] = items or []
    else:
        doc_type = doc_type.strip()
        if not doc_type:
            raise ValueError("Document type cannot be empty.")
        by_type = checklist.setdefault("items", {})
        if items is None:
            by_type.pop(doc_type, None)
        else:
            by_type[doc_type] = items
    save_config(cfg)
