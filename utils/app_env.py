"""
Which settings file this copy of the app uses.

Production (Streamlit Cloud, GitHub Actions) sets nothing and uses config.yaml.
The local dev app (run_dev.bat) sets DOCREGISTRY_CONFIG=config.dev.yaml, which
points at the dev Google Sheet, the local dev WhatsApp sender, the dev WhatsApp
group and dev test numbers — so testing never touches live data or real people.
"""

import os

CONFIG_FILE = os.getenv("DOCREGISTRY_CONFIG", "").strip() or "config.yaml"
IS_DEV = CONFIG_FILE != "config.yaml"
