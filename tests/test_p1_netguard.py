"""Tests for Phase 1: netguard socket interceptor."""
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytest

from trailhead.netguard import (
    OfflineViolation,
    get_blocked_attempts,
    install_netguard,
    reset_blocked_attempts,
    uninstall_netguard,
)

def test_netguard_blocks_external():
    reset_blocked_attempts()
    install_netguard()
    try:
        # Outbound external connection must raise OfflineViolation and increment counter
        with pytest.raises(OfflineViolation):
            socket.create_connection(("example.com", 80), timeout=1.0)
        assert get_blocked_attempts() == 1

        # Second external connection attempt
        with pytest.raises(OfflineViolation):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("8.8.8.8", 53))
        assert get_blocked_attempts() == 2

        # Start a local dummy TCP listener to verify local connection succeeds
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        def accept_conn():
            conn, _ = listener.accept()
            conn.close()

        t = threading.Thread(target=accept_conn, daemon=True)
        t.start()

        client = socket.create_connection(("127.0.0.1", port), timeout=2.0)
        client.close()
        listener.close()

        # Counter should remain 2 (unchanged by local connection)
        assert get_blocked_attempts() == 2

    finally:
        uninstall_netguard()
