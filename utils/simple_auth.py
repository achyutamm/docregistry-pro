"""
Simple Authentication System with cookie-based session persistence and idle timeout.
"""

import json
import streamlit as st
import yaml
from datetime import datetime, timedelta
from utils.password_utils import hash_password, verify_password, is_hashed


class SimpleAuth:
    def __init__(self, config_file='config.yaml', cookie_manager=None):
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        self.users          = self.config.get('users', {})
        self.session_config = self.config.get('session', {})
        self._cm            = cookie_manager   # injected once from app.py

    # ── helpers ──────────────────────────────────────────────────
    def _timeout_minutes(self):
        return int(self.session_config.get('idle_timeout_minutes', 30))

    def _cookie_name(self):
        return self.session_config.get('cookie_name', 'docregistry_session')

    def _write_cookie(self, username: str):
        if self._cm is None:
            return
        data = json.dumps({
            'username':      username,
            'login_time':    st.session_state.get('login_time', datetime.now()).isoformat(),
            'last_activity': datetime.now().isoformat(),
        })
        self._cm.set(
            self._cookie_name(),
            data,
            expires_at=datetime.now() + timedelta(minutes=self._timeout_minutes() + 10),
        )

    def _delete_cookie(self):
        if self._cm is None:
            return
        try:
            self._cm.remove(self._cookie_name())
        except Exception:
            pass

    def _set_session(self, username: str, login_time=None):
        st.session_state.authenticated = True
        st.session_state.username      = username
        st.session_state.user_info     = self.users[username]
        st.session_state.login_time    = login_time or datetime.now()
        st.session_state.last_activity = datetime.now()

    # ── public API ────────────────────────────────────────────────
    def authenticate(self, username, password):
        if username in self.users:
            stored = self.users[username]['password']
            if is_hashed(stored):
                if verify_password(password, stored):
                    return True, self.users[username]
            elif stored == password:
                # Legacy plaintext password — upgrade to a hash now that it's verified
                self.set_user_password(username, password)
                return True, self.users[username]
        return False, None

    def is_authenticated(self) -> bool:
        # --- already authenticated in this session ---
        if st.session_state.get('authenticated', False):
            last_act = st.session_state.get('last_activity')
            if last_act:
                elapsed_min = (datetime.now() - last_act).total_seconds() / 60
                if elapsed_min > self._timeout_minutes():
                    self._delete_cookie()
                    for k in list(st.session_state.keys()):
                        del st.session_state[k]
                    st.warning(
                        f"⚠️ You were logged out after "
                        f"{self._timeout_minutes()} minutes of inactivity."
                    )
                    return False
            st.session_state.last_activity = datetime.now()
            self._write_cookie(st.session_state.username)
            return True

        # --- cookie check ---
        # On first render after a page refresh, the CookieManager iframe hasn't
        # loaded yet, so _cm.get() returns None even if a valid cookie exists.
        # Force ONE extra rerun to let the iframe load, then read the cookie.
        if not st.session_state.get("_cookie_checked", False):
            st.session_state["_cookie_checked"] = True
            st.rerun()

        if self._cm is not None:
            try:
                raw = self._cm.get(self._cookie_name())
                if raw:
                    data        = json.loads(raw)
                    uname       = data.get('username', '')
                    last_act    = datetime.fromisoformat(data.get('last_activity', ''))
                    login_time  = datetime.fromisoformat(data.get('login_time', ''))
                    elapsed_min = (datetime.now() - last_act).total_seconds() / 60
                    if elapsed_min <= self._timeout_minutes() and uname in self.users:
                        self._set_session(uname, login_time)
                        self._write_cookie(uname)
                        return True
                    elif elapsed_min > self._timeout_minutes():
                        # Cookie exists but session timed out
                        self._delete_cookie()
            except Exception:
                pass

        return False

    def login(self):
        if st.session_state.get('authenticated', False):
            return True, st.session_state.user_info

        st.markdown("## 🔐 Login")

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit   = st.form_submit_button("Login", use_container_width=True)

            if submit:
                if username and password:
                    success, user_info = self.authenticate(username, password)
                    if success:
                        self._set_session(username)
                        self._write_cookie(username)
                        st.success(f"✅ Welcome, {user_info['name']}!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
                else:
                    st.warning("⚠️ Please enter both username and password")

        return False, None

    def logout(self):
        self._delete_cookie()
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    def get_user_info(self):
        return st.session_state.get('user_info', {})

    def username_exists(self, username):
        return username in self.users

    def add_user_to_config(self, username, password, name, role, config_access=False, config_file="config.yaml"):
        with open(config_file, "r") as f:
            cfg = yaml.safe_load(f)
        if "users" not in cfg:
            cfg["users"] = {}
        cfg["users"][username] = {
            "password": hash_password(password), "name": name, "role": role,
            "config_access": bool(config_access)
        }
        with open(config_file, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        self.users = cfg["users"]
        return True

    def set_user_config_access(self, username, value: bool, config_file="config.yaml"):
        """Grant or revoke Configuration tab access for an existing user."""
        with open(config_file, "r") as f:
            cfg = yaml.safe_load(f)
        if username not in cfg.get("users", {}):
            return False
        cfg["users"][username]["config_access"] = bool(value)
        with open(config_file, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        self.users = cfg["users"]
        if st.session_state.get("username") == username:
            st.session_state.user_info = self.users[username]
        return True

    def set_user_password(self, username, new_password, config_file="config.yaml"):
        """Hash and persist a new password for an existing user (used for password resets)."""
        with open(config_file, "r") as f:
            cfg = yaml.safe_load(f)
        if username not in cfg.get("users", {}):
            return False
        cfg["users"][username]["password"] = hash_password(new_password)
        with open(config_file, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        self.users = cfg["users"]
        if st.session_state.get("username") == username:
            st.session_state.user_info = self.users[username]
        return True

    def set_user_role(self, username, new_role: str, config_file="config.yaml"):
        with open(config_file, "r") as f:
            cfg = yaml.safe_load(f)
        if username not in cfg.get("users", {}):
            return False
        cfg["users"][username]["role"] = new_role.lower()
        with open(config_file, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        self.users = cfg["users"]
        if st.session_state.get("username") == username:
            st.session_state.user_info = self.users[username]
        return True

    def remove_user_from_config(self, username, config_file="config.yaml"):
        with open(config_file, "r") as f:
            cfg = yaml.safe_load(f)
        if username in cfg.get("users", {}):
            del cfg["users"][username]
            with open(config_file, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
            self.users = cfg.get("users", {})
            return True
        return False
