"""Field-level encryption for personal identifiers (AES-256-GCM with key versions) and keyed fingerprints."""
import base64
import hashlib
import hmac
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import get_settings


def _keys() -> dict[str, bytes]:
    s = get_settings()
    if s.field_encryption_keys:
        return {k: base64.b64decode(v) for k, v in json.loads(s.field_encryption_keys).items()}
    # Development / test only (production refuses to start without explicit keys).
    derived = HKDF(hashes.SHA256(), 32, salt=None, info=b"sims-field-encryption").derive(s.secret_key.encode())
    return {"1": derived}


def encrypt(plaintext: str) -> bytes:
    s = get_settings()
    keys = _keys()
    version = s.field_encryption_active if s.field_encryption_active in keys else next(iter(keys))
    nonce = os.urandom(12)
    ct = AESGCM(keys[version]).encrypt(nonce, plaintext.encode(), version.encode())
    return len(version).to_bytes(1, "big") + version.encode() + nonce + ct


def decrypt(blob: bytes) -> str:
    n = blob[0]
    version, rest = blob[1:1 + n].decode(), blob[1 + n:]
    return AESGCM(_keys()[version]).decrypt(rest[:12], rest[12:], version.encode()).decode()


def fingerprint(value: str) -> str:
    s = get_settings()
    key = (s.fingerprint_key or s.secret_key).encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
