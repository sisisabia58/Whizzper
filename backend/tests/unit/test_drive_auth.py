import pytest
import os
from modules.utils.drive_auth import encrypt_token, decrypt_token

def test_encryption_roundtrip(monkeypatch):
    monkeypatch.setenv("DRIVE_TOKEN_ENC_KEY", "u-6bM0kZl847-qA6u9Q2h6_wHmxrX2r8Y6qB3k5i6u0=")
    plain = "ya29.a0AfB_byD..."
    enc = encrypt_token(plain)
    assert enc != plain.encode()
    assert decrypt_token(enc) == plain
