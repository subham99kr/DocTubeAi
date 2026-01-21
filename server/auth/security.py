import os
from datetime import datetime, timedelta, timezone 
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError


# 1. secret key
SECRET_KEY = os.getenv("SECRET_KEY", "your-master-password")


# 2. algo
ALGORITHM = "HS256"

def create_secure_jwt(oauth_id: str):
    expire = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {
        "sub": oauth_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        # "iss": "doctubeai",
        # "aud": "doctubeai-client"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_oauth_id_from_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except (ExpiredSignatureError,JWTError):
        return None
