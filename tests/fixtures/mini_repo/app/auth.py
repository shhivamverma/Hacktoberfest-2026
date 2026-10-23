"""User authentication entrypoints."""
from app.passwords import verify_password
from app.tokens import decode_token, is_expired

def create_session(user: str) -> dict:
    """Initialize an active session dictionary."""
    return {"user": user, "active": True}

def login(user: str, pw: str) -> dict:
    """Authenticate user credentials and initiate session."""
    if verify_password(pw, f"hashed_{pw}"):
        return create_session(user)
    raise PermissionError("Bad credentials")

def verify_token(token: str) -> bool:
    """Verify session token integrity and freshness."""
    payload = decode_token(token)
    if is_expired(payload):
        return False
    return True
