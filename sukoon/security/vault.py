"""
Project Sukoon — Authenticated Security Vault (AES-256-GCM)
Protects API keys and secrets; strictly redacts sensitive tokens from logs.
"""
from __future__ import annotations

import base64
import os
import re
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecurityVault:
    """AES-256-GCM authenticated encryption engine for server-side secret storage."""

    def __init__(self, master_key_hex: Optional[str] = None) -> None:
        if master_key_hex:
            self._key = bytes.fromhex(master_key_hex)
        else:
            # Generate 256-bit key
            self._key = AESGCM.generate_key(bit_length=256)
        self._aesgcm = AESGCM(self._key)

    @property
    def key_hex(self) -> str:
        return self._key.hex()

    def encrypt(self, plaintext: str) -> str:
        """Encrypt secret with AES-256-GCM using 96-bit random nonce."""
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode("ascii")

    def decrypt(self, encoded_ciphertext: str) -> str:
        """Decrypt and verify authentication tag."""
        raw = base64.b64decode(encoded_ciphertext.encode("ascii"))
        nonce = raw[:12]
        ciphertext = raw[12:]
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")


class SecretRedactor:
    """Scans text and redacts API keys, secret hashes, and credentials from logs."""

    PATTERNS = [
        re.compile(r"(PK[A-Z0-9]{18,})", re.IGNORECASE), # Alpaca API Key pattern
        re.compile(r"(sk-[a-zA-Z0-9]{24,})", re.IGNORECASE), # Secret key pattern
        re.compile(r"([0-9a-f]{64})", re.IGNORECASE), # 64-char hex strings / tokens
    ]

    @classmethod
    def redact(cls, text: str) -> str:
        masked = text
        for p in cls.PATTERNS:
            masked = p.sub("[REDACTED_SECRET]", masked)
        return masked
