"""Share link tokens (ADR-005 §10, docs/ACCESS_PLAN_R4-R7.md stage 2).

token = base64url(share_id 16 bytes) + base64url(HMAC-SHA256(ARDOR_SHARE_SECRET, share_id)[:24])
The token is never stored: the server recomputes it from the share id, so the same
link can be copied again, and rotating ARDOR_SHARE_SECRET invalidates every link.
"""
import base64
import binascii
import hashlib
import hmac
import uuid
from typing import Optional

from services.api.config import settings

_ID_CHARS = 22   # 16 bytes
_MAC_BYTES = 24
_MAC_CHARS = 32  # 24 bytes
TOKEN_LENGTH = _ID_CHARS + _MAC_CHARS


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(raw_id: bytes) -> bytes:
    return hmac.new(settings.share_secret.encode("utf-8"), b"ardor-share-v1:" + raw_id, hashlib.sha256).digest()[:_MAC_BYTES]


def share_token(share_id: str) -> str:
    raw_id = uuid.UUID(share_id).bytes
    return _b64(raw_id) + _b64(_mac(raw_id))


def share_id_from_token(token: str) -> Optional[str]:
    """Return the share id for an authentic token, otherwise None (constant-time MAC check)."""
    if not isinstance(token, str) or len(token) != TOKEN_LENGTH:
        return None
    try:
        raw_id = _unb64(token[:_ID_CHARS])
        mac = _unb64(token[_ID_CHARS:])
    except (binascii.Error, ValueError):
        return None
    if len(raw_id) != 16 or len(mac) != _MAC_BYTES or not hmac.compare_digest(mac, _mac(raw_id)):
        return None
    return str(uuid.UUID(bytes=raw_id))


def share_url(share_id: str) -> str:
    return f"{settings.public_origin.rstrip('/')}/s/{share_token(share_id)}"


def legacy_share_url(log_no: str) -> str:
    return f"{settings.public_origin.rstrip('/')}/share/{log_no}"
