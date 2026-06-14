"""
Password hashing for config.yaml user records (PBKDF2-HMAC-SHA256, stdlib only).
"""

import hashlib
import hmac
import secrets

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 260000
_RESET_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, hash_hex = stored.split("$")
        if algo != _ALGO:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(digest.hex(), hash_hex)
    except ValueError:
        return False


def is_hashed(stored: str) -> bool:
    return stored.startswith(f"{_ALGO}$")


def generate_temp_password(length: int = 10) -> str:
    """Generate a random password for password-reset emails."""
    return "".join(secrets.choice(_RESET_PASSWORD_ALPHABET) for _ in range(length))
