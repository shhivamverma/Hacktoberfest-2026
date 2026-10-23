"""Tests for authentication flows."""
from app.auth import login, verify_token

def test_login_ok():
    res = login("alice", "secret")
    assert res["active"] is True

def test_verify_token_expired():
    expired = "alice.500"
    assert verify_token(expired) is False
