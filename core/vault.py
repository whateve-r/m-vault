# secure API key storage and retrieval (AES encryption)

from cryptography.fernet import Fernet
import os

# Generate or load encryption key
KEY_FILE = "data/secret.key"

def load_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    else:
        with open(KEY_FILE, "rb") as f:
            key = f.read()
    return Fernet(key)

fernet = load_key()

def encrypt_api_key(api_key: str) -> str:
    return fernet.encrypt(api_key.encode()).decode()

def decrypt_api_key(enc_api_key: str) -> str:
    return fernet.decrypt(enc_api_key.encode()).decode()
