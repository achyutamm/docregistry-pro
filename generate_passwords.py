"""
Generate hashed passwords for config.yaml
Run this once to get proper password hashes
"""

import streamlit_authenticator as stauth

# Plain text passwords
passwords = ['admin123', 'staff123']

# Generate hashed passwords
hashed_passwords = stauth.Hasher(passwords).generate()

print("\n" + "="*60)
print("COPY THESE HASHED PASSWORDS TO config.yaml")
print("="*60)
print("\nFor admin (password: admin123):")
print(hashed_passwords[0])
print("\nFor staff1 (password: staff123):")
print(hashed_passwords[1])
print("\n" + "="*60)
