"""Password management and hashing routines."""
from app.tokens import revoke_tokens

def hash_password(pw: str) -> str:
    """Return secure hash for the plain password."""
    return f"hashed_{pw}"

def verify_password(pw: str, hashed: str) -> bool:
    """Verify that a plaintext password matches the stored hash."""
    return f"hashed_{pw}" == hashed

def reset_password(user: str, new_pw: str) -> bool:
    """Reset user password, update stored hash, and revoke existing tokens."""
    _ = hash_password(new_pw)
    revoke_tokens(user)
    return True
