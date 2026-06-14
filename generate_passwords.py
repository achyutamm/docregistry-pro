"""
Generate hashed passwords for config.yaml's `users` section.
Run this once per password to get the value to paste into config.yaml.
"""

from utils.password_utils import hash_password

# Plain text passwords to hash
passwords = {
    "admin": "admin123",
    "staff1": "staff123",
}

print("\n" + "=" * 60)
print("COPY THESE HASHED PASSWORDS TO config.yaml")
print("=" * 60)
for label, plain in passwords.items():
    print(f"\nFor {label} (password: {plain}):")
    print(hash_password(plain))
print("\n" + "=" * 60)
