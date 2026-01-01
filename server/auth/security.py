import os
import base64
from datetime import datetime, timedelta, timezone 
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
from jose import jwt

# 1. Setup Keys
SECRET_KEY = os.getenv("SECRET_KEY", "your-master-password")
SALT = os.getenv("STATIC_SALT", "at-least-16-chars-long-salt").encode()

# 2. Derive Encryption Key (Salted)
kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=SALT,
    iterations=100000,
)
encryption_key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY.encode()))
cipher = Fernet(encryption_key)

# 3. JWT Logic
ALGORITHM = "HS256"

def create_secure_jwt(oauth_id: str):
    """Encrypts ID and creates a timezone-aware JWT."""
    encrypted_id = cipher.encrypt(oauth_id.encode()).decode()
    
    expire = datetime.now(timezone.utc) + timedelta(days=1)
    
    to_encode = {"sub": encrypted_id, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_oauth_id_from_token(token: str):
    """Decodes JWT and decrypts the salted ID."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        encrypted_id = payload.get("sub")
        return cipher.decrypt(encrypted_id.encode()).decode()
    except Exception:
        return None