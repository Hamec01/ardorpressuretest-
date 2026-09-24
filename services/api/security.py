"""Small cryptographic helpers shared by auth and server-session code.

The raw opaque value is returned only to the caller that must deliver it to a client.
Only its SHA-256 digest is suitable for persistence.
"""

import hashlib
import hmac
import secrets


def generate_opaque_secret() -> str:
    """Return a dot-free, unpadded base64url secret backed by 256 CSPRNG bits."""
    return secrets.token_urlsafe(32)


def hash_opaque_secret(secret: str) -> str:
    """Return the lowercase SHA-256 hex digest used for indexed persistence."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def compare_secret_hashes(a: str, b: str) -> bool:
    """Compare two already-computed, fixed-length digests in constant time."""
    return hmac.compare_digest(a, b)
