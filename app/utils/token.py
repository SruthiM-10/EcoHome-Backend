# # app/utils/token.py
# import os
# from datetime import datetime, timedelta, timezone
# from jose import jwt
# from pathlib import Path
# from dotenv import load_dotenv

# # Load .env (adjust if your .env is elsewhere)
# load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change")
# ALGORITHM = os.getenv("ALGORITHM", "HS256")
# ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
#     to_encode = data.copy()
#     expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
#     to_encode.update({"exp": expire})
#     assert SECRET_KEY, "SECRET_KEY is empty"
#     assert ALGORITHM in {"HS256","HS384","HS512","RS256","RS384","RS512"}, f"Bad ALGO: {ALGORITHM}"
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

import os
from datetime import datetime, timedelta, timezone
from jose import jwt
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

#email verification token (short‑lived, 24h)
def create_email_token(email: str, ttl_hours: int = 24) -> str:
    payload = {
        "sub": email,
        "purpose": "verify",
        "exp": datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
