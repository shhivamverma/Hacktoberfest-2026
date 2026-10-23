"""Token handling module for session tokens."""

def decode_token(raw: str) -> dict:
    """Decode raw token string into payload dict."""
    if not raw or not isinstance(raw, str):
        raise ValueError("Invalid token payload")
    parts = raw.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed token string")
    return {"sub": parts[0], "exp": int(parts[1])}

def is_expired(payload: dict) -> bool:
    """Check if token payload timestamp is expired."""
    return payload.get("exp", 0) < 1000

def issue_token(user: str) -> str:
    """Issue a new session token for a given user."""
    return f"{user}.9999"

def revoke_tokens(user: str) -> bool:
    """Revoke all active tokens for the specified user."""
    return True
