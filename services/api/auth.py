import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from services.api.config import settings
from services.api.database import get_db
from services.api.models import User

security_bearer = HTTPBearer(auto_error=False)

# --- password hashing: Argon2id (current), PBKDF2-HMAC-SHA256 (legacy, verify-only) -

_ARGON2ID_PREFIX = "$argon2id$"
_ARGON2_TIME_COST = 3
_ARGON2_MEMORY_COST_KIB = 12288
_ARGON2_PARALLELISM = 1
_argon2_hasher = PasswordHasher(
    time_cost=_ARGON2_TIME_COST,
    memory_cost=_ARGON2_MEMORY_COST_KIB,
    parallelism=_ARGON2_PARALLELISM,
)

# Fixed, valid Argon2id hash of an arbitrary, well-known non-secret string - not a real
# password and not anyone's credential. Exists only so a future login handler can run a
# real (dummy) Argon2id verification even when the submitted username does not exist,
# keeping response timing consistent between "unknown user" and "wrong password" and
# closing a username-enumeration timing side-channel. No login path uses this yet.
DUMMY_ARGON2_HASH = (
    "$argon2id$v=19$m=12288,t=3,p=1$q87mjs0Xl7fxdwVNTDok2Q$"
    "vLBgeqqKz8seKDobnvedpy5ABxDOwxyseN8xCE5ZDdg"
)


def hash_password(password: str) -> str:
    """Хеширует пароль Argon2id (m=12288 KiB, t=3, p=1). argon2-cffi генерирует новую
    случайную соль при каждом вызове внутри PasswordHasher.hash() - хеш одного и того
    же пароля всегда различается между вызовами. Пароль передаётся как есть: без trim
    и без Unicode-нормализации."""
    return _argon2_hasher.hash(password)


def _verify_password_pbkdf2(password: str, stored_hash: str) -> bool:
    """Legacy PBKDF2-HMAC-SHA256 verification - algorithm unchanged from before the
    Argon2id cutover, kept only to verify hashes created before it. Never used to
    create a new hash any more; hash_password() always produces Argon2id output."""
    try:
        salt, hashed = stored_hash.split('$', 1)
        expected = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return hmac.compare_digest(hashed, expected)
    except Exception:
        return False


def _verify_password_argon2id(password: str, stored_hash: str) -> bool:
    try:
        _argon2_hasher.verify(stored_hash, password)
        return True
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False
    except Exception:
        # argon2-cffi's own exception hierarchy covers wrong-password/malformed-hash
        # cases above; anything else (e.g. a non-Argon2id string that still happened to
        # start with the prefix) must still fail closed, not raise, and never surface
        # the underlying exception text - see check_password_with_upgrade()'s docstring
        # and the module-level "safe 401 text" boundary this file is held to.
        return False


def verify_password(password: str, stored_hash: str) -> bool:
    """Проверяет пароль против текущего Argon2id ($argon2id$...) или legacy PBKDF2
    (salt$hash) хеша - формат определяется по префиксу хранимого значения. Повреждённые
    или неизвестные форматы (ни один из двух распознаваемых префиксов/структур) безопасно
    возвращают False, никогда не поднимают исключение."""
    if not stored_hash:
        return False
    if stored_hash.startswith(_ARGON2ID_PREFIX):
        return _verify_password_argon2id(password, stored_hash)
    return _verify_password_pbkdf2(password, stored_hash)


@dataclass
class PasswordCheckResult:
    ok: bool
    upgraded_hash: Optional[str] = None  # set only when ok=True and stored_hash was legacy PBKDF2


def check_password_with_upgrade(password: str, stored_hash: str) -> PasswordCheckResult:
    """Чистая функция: проверяет `password` против `stored_hash` (Argon2id или legacy
    PBKDF2, тем же способом, что и verify_password()) и, только если совпадение
    произошло против legacy PBKDF2-хеша, дополнительно вычисляет новый Argon2id-хеш
    того же пароля для вызывающей стороны. Для уже актуального Argon2id-хеша
    upgraded_hash остаётся None - обновление не требуется. Ничего не читает и не
    записывает в БД и не имеет иных побочных эффектов - решение о том, сохранять ли
    upgraded_hash и в какой транзакции, остаётся полностью за вызывающим кодом (в
    будущем login-потоке - та же транзакция, что создание сессии)."""
    if not stored_hash:
        return PasswordCheckResult(ok=False)
    if stored_hash.startswith(_ARGON2ID_PREFIX):
        ok = _verify_password_argon2id(password, stored_hash)
        return PasswordCheckResult(ok=ok)

    ok = _verify_password_pbkdf2(password, stored_hash)
    if not ok:
        return PasswordCheckResult(ok=False)
    return PasswordCheckResult(ok=True, upgraded_hash=hash_password(password))


# --- new-password validation: length only, no trim, no normalization ----------------

PASSWORD_MIN_LENGTH = 6
PASSWORD_MAX_LENGTH = 128


def validate_new_password(password: str) -> Optional[str]:
    """Проверяет длину нового пароля в Unicode codepoints (len() на str в Python уже
    считает codepoints, не байты и не grapheme clusters) - ровно 6..128 включительно.
    Пароль никогда не обрезается и не подвергается Unicode-нормализации ни здесь, ни
    где-либо ниже по цепочке хеширования - пробелы (включая ведущие/замыкающие) и любые
    другие codepoints считаются полноценными символами пароля. Чистая функция: не
    обращается к БД, ничего не логирует (в частности, никогда не логирует и не включает
    в возвращаемое сообщение содержимое самого пароля). Возвращает None, если пароль
    допустим, иначе безопасное (без содержимого пароля) сообщение о нарушенном
    ограничении."""
    length = len(password)
    if length < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if length > PASSWORD_MAX_LENGTH:
        return f"Password must be at most {PASSWORD_MAX_LENGTH} characters."
    return None


# --- opaque secrets: session/refresh/CSRF tokens - generate, hash, compare ----------

def generate_opaque_secret() -> str:
    """>=256-bit (32-byte) CSPRNG-sourced opaque secret via secrets.token_urlsafe(32)
    (itself backed by secrets.token_bytes(32)), URL-safe base64 with padding stripped.
    The URL-safe base64 alphabet (A-Za-z0-9-_) contains no '.' by construction, so this
    value can never be mistaken for a dot-separated JWT by a naive shape check. This is
    the raw secret to hand to a client (cookie value / desktop refresh credential) -
    only its hash (hash_opaque_secret()) is ever meant to be persisted."""
    return secrets.token_urlsafe(32)


def hash_opaque_secret(secret: str) -> str:
    """SHA-256 hex digest (64 lowercase hex chars) of an opaque secret - the only form
    of it that should ever be persisted or looked up in storage."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def compare_secret_hashes(a: str, b: str) -> bool:
    """Constant-time comparison of two already-computed hash values - e.g. a freshly
    hashed presented secret against a stored hash. Never compare raw secrets or their
    hashes with `==`."""
    return hmac.compare_digest(a, b)


def create_access_token(data: dict, expires_delta_seconds: int = 86400 * 7) -> str:
    """Создаёт подписанный JWT токен."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = data.copy()
    payload["exp"] = int(time.time()) + expires_delta_seconds
    payload["iat"] = int(time.time())

    def b64_encode(obj: dict) -> str:
        s = json.dumps(obj, separators=(',', ':'), sort_keys=True)
        return base64.urlsafe_b64encode(s.encode('utf-8')).decode('utf-8').rstrip('=')

    header_b64 = b64_encode(header)
    payload_b64 = b64_encode(payload)
    message = f"{header_b64}.{payload_b64}"

    signature = hmac.new(
        settings.secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')

    return f"{message}.{sig_b64}"


def decode_access_token(token: str) -> dict:
    """Декодирует и верифицирует подпись JWT токена."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid token structure")

        message = f"{parts[0]}.{parts[1]}"
        expected_sig = hmac.new(
            settings.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode('utf-8').rstrip('=')

        if not hmac.compare_digest(parts[2], expected_sig_b64):
            raise ValueError("Invalid signature")

        # Decode payload
        rem = len(parts[1]) % 4
        padded = parts[1] + ('=' * (4 - rem) if rem > 0 else '')
        payload_bytes = base64.urlsafe_b64decode(padded.encode('utf-8'))
        payload = json.loads(payload_bytes.decode('utf-8'))

        if payload.get("exp") and payload["exp"] < time.time():
            raise ValueError("Token expired")

        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication credentials invalid: {e}"
        )


# --- desktop access JWT: short-lived, session-bound, own strict verifier ------------
#
# Deliberately does NOT reuse decode_access_token()/get_current_user() - this keeps
# create_access_token()'s and decode_access_token()'s existing contract completely
# unmodified (including its current error-message shape), while giving the desktop
# token its own independent, stricter rules: a mandatory typ claim, a mandatory sid
# claim tying it to a future server-side session record, and a hard 401-equivalent
# reject on anything that doesn't match exactly. Nothing below is wired into any route
# or FastAPI dependency yet - these are the primitives only.

DESKTOP_ACCESS_TOKEN_TYPE = "desktop_access"
DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS = 15 * 60  # exactly 15 minutes
_DESKTOP_TOKEN_MAX_LENGTH = 4096  # cheap DoS guard - rejected before any decode work
_DESKTOP_TOKEN_MAX_CLOCK_SKEW_SECONDS = 30


def _encode_desktop_access_token(payload: dict) -> str:
    """Encode and sign a desktop JWT without changing the legacy JWT helpers."""
    header = {"alg": "HS256", "typ": "JWT"}

    def b64_encode(obj: dict) -> str:
        serialized = json.dumps(obj, separators=(",", ":"), sort_keys=True)
        return base64.urlsafe_b64encode(serialized.encode("utf-8")).decode("utf-8").rstrip("=")

    header_b64 = b64_encode(header)
    payload_b64 = b64_encode(payload)
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{message}.{signature_b64}"


def create_desktop_access_token(user_id: str, session_id: str) -> str:
    """Создаёт desktop access JWT сроком ровно 15 минут. Обязательные payload claims:
    typ="desktop_access", sub=<user_id>, sid=<session_id>, iat, exp. Время считывается
    ровно один раз, поэтому exp - iat всегда равно 900 даже на границе смены секунды.
    Роль пользователя намеренно не включается - авторизация впоследствии должна
    определяться заново по sub/sid, не читаться из содержимого токена. Legacy-функции
    create_access_token()/decode_access_token() не используются и не изменяются.

    user_id/session_id - это внутренние идентификаторы, которые формирует только
    доверенный серверный код (не конечный пользователь напрямую), поэтому здесь
    уместно поднять исключение при нарушении контракта, а не возвращать безопасный
    код ошибки, как это делает verify_desktop_access_token() для недоверенного входа."""
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("user_id must be a non-empty string")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("session_id must be a non-empty string")
    now = int(time.time())
    return _encode_desktop_access_token(
        {
            "typ": DESKTOP_ACCESS_TOKEN_TYPE,
            "sub": user_id,
            "sid": session_id,
            "iat": now,
            "exp": now + DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
        }
    )


class DesktopAccessTokenError(Enum):
    MISSING_OR_INVALID_STRUCTURE = "missing_or_invalid_structure"
    INVALID_HEADER = "invalid_header"
    INVALID_SIGNATURE = "invalid_signature"
    WRONG_TYPE = "wrong_type"
    INVALID_CLAIM = "invalid_claim"
    EXPIRED = "expired"


@dataclass
class DesktopAccessTokenResult:
    ok: bool
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[DesktopAccessTokenError] = None


_JWT_DECODE_FAILED = object()


def _decode_jwt_json_segment(segment_b64: str):
    """Best-effort base64url+JSON decode of one '.'-delimited JWT segment. Returns the
    parsed JSON value on success - which may legitimately be any JSON type (object,
    array, string, number, null), not necessarily an object - or the sentinel
    _JWT_DECODE_FAILED on any decoding failure. Never raises."""
    try:
        rem = len(segment_b64) % 4
        padded = segment_b64 + ("=" * (4 - rem) if rem else "")
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return _JWT_DECODE_FAILED


def _is_strict_int(value) -> bool:
    """True only for a genuine int - excludes bool (a Python int subclass) and any
    other numeric-ish type (float, numeric string, ...)."""
    return isinstance(value, int) and not isinstance(value, bool)


def verify_desktop_access_token(token) -> DesktopAccessTokenResult:
    """Строгая, полностью самостоятельная проверка desktop access JWT. Принимает
    значение произвольного Python-типа (не только str) и никогда не поднимает
    исключение - любой некорректный вход возвращает DesktopAccessTokenResult(ok=False,
    error=<фиксированный код>), без сырого токена, подписи или чего-либо похожего на
    хеш/секрет в возвращаемом значении. Роль из токена не читается вовсе (её там и нет)
    и не может использоваться для авторизации. Не читает и не изменяет БД; ничего не
    знает о таблице sessions - сопоставление sid с реальной записью сессии остаётся
    задачей вызывающего кода на более позднем этапе.

    Порядок проверок:
      1. token - строка не длиннее _DESKTOP_TOKEN_MAX_LENGTH символов (дешёвая защита
         от чрезмерно больших входов, до какой-либо декодирующей работы).
      2. Ровно три '.'-разделённых сегмента.
      3. header декодируется как JSON-объект с alg="HS256" и typ="JWT" - строго; любая
         другая форма (не объект, отсутствующий/неверный alg или typ) - INVALID_HEADER.
      4. Подпись (HMAC-SHA256 над "header.payload") верна - constant-time сравнение.
      5. payload декодируется как JSON-объект - иначе INVALID_CLAIM.
      6. payload["typ"] == "desktop_access" - иначе WRONG_TYPE.
      7. sub/sid - непустые строки; iat/exp - именно int (не bool); exp - iat == 900
         секунд ровно; iat не более чем на _DESKTOP_TOKEN_MAX_CLOCK_SKEW_SECONDS в
         будущем относительно текущего времени сервера - любое нарушение здесь даёт
         INVALID_CLAIM.
      8. now >= exp - EXPIRED.
    """
    try:
        if not isinstance(token, str):
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.MISSING_OR_INVALID_STRUCTURE)
        if len(token) > _DESKTOP_TOKEN_MAX_LENGTH:
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.MISSING_OR_INVALID_STRUCTURE)

        parts = token.split(".")
        if len(parts) != 3:
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.MISSING_OR_INVALID_STRUCTURE)
        header_b64, payload_b64, sig_b64 = parts

        header = _decode_jwt_json_segment(header_b64)
        if header is _JWT_DECODE_FAILED:
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.MISSING_OR_INVALID_STRUCTURE)
        if not isinstance(header, dict) or header.get("alg") != "HS256" or header.get("typ") != "JWT":
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.INVALID_HEADER)

        message = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            settings.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")
        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.INVALID_SIGNATURE)

        payload = _decode_jwt_json_segment(payload_b64)
        if payload is _JWT_DECODE_FAILED:
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.MISSING_OR_INVALID_STRUCTURE)
        if not isinstance(payload, dict):
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.INVALID_CLAIM)

        if payload.get("typ") != DESKTOP_ACCESS_TOKEN_TYPE:
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.WRONG_TYPE)

        sub = payload.get("sub")
        sid = payload.get("sid")
        iat = payload.get("iat")
        exp = payload.get("exp")

        if not isinstance(sub, str) or not sub:
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.INVALID_CLAIM)
        if not isinstance(sid, str) or not sid:
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.INVALID_CLAIM)
        if not _is_strict_int(iat) or not _is_strict_int(exp):
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.INVALID_CLAIM)
        if exp - iat != DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS:
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.INVALID_CLAIM)

        now = time.time()
        if iat > now + _DESKTOP_TOKEN_MAX_CLOCK_SKEW_SECONDS:
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.INVALID_CLAIM)
        if now >= exp:
            return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.EXPIRED)

        return DesktopAccessTokenResult(ok=True, user_id=sub, session_id=sid)
    except Exception:
        # Belt-and-suspenders: every recognized failure mode above already returns a
        # safe enum result without raising. This outer guard exists so that literally
        # no Python value of any type can ever propagate a raw exception - and
        # therefore never any raw token/internal content - out of this function.
        return DesktopAccessTokenResult(ok=False, error=DesktopAccessTokenError.MISSING_OR_INVALID_STRUCTURE)


def seed_default_users(db: Session) -> None:
    """Инициализирует базовых пользователей ARDOR при первом запуске."""
    defaults = [
        ("admin", "admin123", "System Administrator", "admin", "admin@ardor.fi"),
        ("foreman_matti", "foreman123", "Matti Meikäläinen (Foreman)", "foreman", "matti@ardor.fi"),
        ("operator_pekka", "operator123", "Pekka Virtanen (Operator)", "operator", "pekka@ardor.fi"),
    ]
    for username, password, full_name, role, email in defaults:
        existing = db.query(User).filter(User.username == username).first()
        if not existing:
            u = User(
                username=username,
                hashed_password=hash_password(password),
                full_name=full_name,
                role=role,
                email=email,
                is_active=True
            )
            db.add(u)
    db.commit()


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Возвращает текущего аутентифицированного пользователя или None, если токен не передан."""
    if not auth or not auth.credentials or auth.credentials in ("null", "undefined", "None", ""):
        return None

    try:
        payload = decode_access_token(auth.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return db.query(User).filter(User.id == user_id, User.is_active == True).first()
    except Exception:
        return None


def require_role(allowed_roles: List[str]):
    """Защитный декоратор RBAC для маршрутов FastAPI.

    Fail-closed: отсутствующий, пустой, невалидный или просроченный токен, а также
    неизвестный или неактивный пользователь всегда дают 401. Недостаточная роль даёт 403.
    Никакого fallback-пользователя не существует ни в одной ветке.
    """
    def role_checker(
        auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
        db: Session = Depends(get_db)
    ) -> User:
        if not auth or not auth.credentials or auth.credentials in ("null", "undefined", "None", ""):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        payload = decode_access_token(auth.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
            )
        return user
    return role_checker


def require_authenticated_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """Проверяет активную сессию любого авторизованного сотрудника (operator, foreman, manager, admin)."""
    checker = require_role(["operator", "foreman", "manager", "admin"])
    return checker(auth, db)
