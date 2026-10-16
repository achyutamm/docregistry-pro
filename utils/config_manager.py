"""
Safe read/modify/write helpers for config.yaml's editable lookup lists.

Used by the admin-only "Configuration" section in app.py so non-technical
users can manage document types, party names, SRO offices, admin emails,
and the Telegram toggle without hand-editing YAML.
"""
import re
import yaml

from utils.app_env import CONFIG_FILE  # config.yaml, or config.dev.yaml in dev


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


def set_whatsapp_contact_numbers(contacts):
    """Office contacts printed in messages ({contact_numbers}), in the given order.
    contacts: [{"title", "name", "number"}] (a plain number string is also accepted)."""
    def _text(v):   # table cells can arrive as None / NaN for empty
        s = " ".join(str(v if v is not None else "").split())
        return "" if s.lower() in ("nan", "none") else s

    cleaned, seen = [], set()
    for row, raw in enumerate(contacts or [], start=1):
        c = raw if isinstance(raw, dict) else {"number": raw}
        title, name, n = _text(c.get("title")), _text(c.get("name")), _text(c.get("number"))
        if not n:
            if name:
                raise ValueError(f"Row {row}: enter a contact number for {name}.")
            continue
        digits = "".join(ch for ch in n if ch.isdigit())
        if not re.fullmatch(r"\+?[\d ]+", n) or not 6 <= len(digits) <= 15:
            raise ValueError(f"Row {row}: '{n}' is not a valid phone number (digits, optional + and spaces).")
        if n in seen:
            raise ValueError(f"Row {row}: {n} is listed twice.")
        seen.add(n)
        cleaned.append({"title": title, "name": name, "number": n})
    cfg = load_config()
    cfg.setdefault("whatsapp", {})["contact_numbers"] = cleaned
    save_config(cfg)


def set_party1_checklist_test_mode(enabled: bool, recipients):
    """Test mode sends every checklist to these people instead of Party 1.
    recipients: [{"name", "country_code", "mobile"}]; blank rows are ignored."""
    from utils import phone_utils
    def _text(v):   # table cells can arrive as None / NaN for empty
        s = " ".join(str(v if v is not None else "").split())
        return "" if s.lower() in ("nan", "none") else s

    cleaned, seen = [], set()
    for n, r in enumerate(recipients or [], start=1):
        name = _text(r.get("name"))
        code = _text(r.get("country_code")) or phone_utils.DEFAULT_CODE
        mobile = _text(r.get("mobile"))
        if not name and not mobile:
            continue
        if not name:
            raise ValueError(f"Row {n}: enter the person's name for {mobile}.")
        if not mobile:
            raise ValueError(f"Row {n}: enter a mobile number for {name}.")
        error = phone_utils.validate(code, mobile)
        if error:
            raise ValueError(f"Row {n} ({name}): {error}")
        key = phone_utils.join(code, mobile)
        if key in seen:
            raise ValueError(f"Row {n} ({name}): {code} {mobile} is listed twice.")
        seen.add(key)
        cleaned.append({"name": name, "country_code": phone_utils.clean_code(code), "mobile": mobile})
    if enabled and not cleaned:
        raise ValueError("Add at least one test recipient (name + mobile) to turn test mode on.")
    cfg = load_config()
    p1 = cfg.setdefault("party1_checklist", {})
    p1["test_mode"] = bool(enabled)
    p1["test_recipients"] = cleaned
    p1.pop("test_mobile", None)          # replaced by test_recipients
    p1.pop("test_country_code", None)
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
