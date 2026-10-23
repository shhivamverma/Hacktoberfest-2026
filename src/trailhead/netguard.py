"""Network guard to enforce 100% offline local runtime execution."""
import os
import socket
from typing import Any, Tuple

class OfflineViolation(RuntimeError):
    """Raised when an attempt is made to establish a non-localhost network connection."""
    pass

_BLOCKED_ATTEMPTS = 0
_INSTALLED = False

_ORIG_CONNECT = socket.socket.connect
_ORIG_CREATE_CONNECTION = socket.create_connection

def _is_local_host(host: Any) -> bool:
    """Check if destination host is localhost."""
    if host is None:
        return True
    if not isinstance(host, str):
        return False
    clean = host.strip().lower()
    return clean in ("127.0.0.1", "::1", "localhost", "0.0.0.0")

def _guarded_connect(self, address, *args, **kwargs):
    global _BLOCKED_ATTEMPTS
    host = address[0] if isinstance(address, (tuple, list)) and len(address) > 0 else address
    if not _is_local_host(host):
        _BLOCKED_ATTEMPTS += 1
        raise OfflineViolation(f"OfflineViolation: Outbound network request to '{host}' blocked by Trailhead netguard.")
    return _ORIG_CONNECT(self, address, *args, **kwargs)

def _guarded_create_connection(address, *args, **kwargs):
    global _BLOCKED_ATTEMPTS
    host = address[0] if isinstance(address, (tuple, list)) and len(address) > 0 else address
    if not _is_local_host(host):
        _BLOCKED_ATTEMPTS += 1
        raise OfflineViolation(f"OfflineViolation: Outbound connection to '{host}' blocked by Trailhead netguard.")
    return _ORIG_CREATE_CONNECTION(address, *args, **kwargs)

def install_netguard() -> None:
    """Install socket patches to restrict all connections to localhost."""
    global _INSTALLED
    if os.environ.get("TRAILHEAD_OFFLINE", "1") == "0":
        return
    if not _INSTALLED:
        socket.socket.connect = _guarded_connect
        socket.create_connection = _guarded_create_connection
        _INSTALLED = True

def uninstall_netguard() -> None:
    """Uninstall socket patches."""
    global _INSTALLED
    if _INSTALLED:
        socket.socket.connect = _ORIG_CONNECT
        socket.create_connection = _ORIG_CREATE_CONNECTION
        _INSTALLED = False

def get_blocked_attempts() -> int:
    """Return count of blocked non-localhost network attempts."""
    return _BLOCKED_ATTEMPTS

def reset_blocked_attempts() -> None:
    """Reset the blocked attempts counter."""
    global _BLOCKED_ATTEMPTS
    _BLOCKED_ATTEMPTS = 0
