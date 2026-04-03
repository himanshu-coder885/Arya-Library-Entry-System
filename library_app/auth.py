import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta

from library_app.config import (
    ADMIN_CONFIG_FILE,
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
)


SESSIONS = {}
PASSWORD_RESET_OTP = {}
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 390000
SESSION_TIMEOUT = timedelta(hours=8)


def _default_credentials():
    username = os.environ.get("LIBRARY_ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME).strip() or DEFAULT_ADMIN_USERNAME
    password = os.environ.get("LIBRARY_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    email = os.environ.get("LIBRARY_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).strip()
    return {
        "username": username,
        "password_hash": hash_password(password),
        "email": email,
    }


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return f"{PASSWORD_HASH_PREFIX}${PASSWORD_HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, password_hash):
    if not password_hash:
        return False

    try:
        algorithm, iterations_text, salt_hex, digest_hex = password_hash.split("$", 3)
    except ValueError:
        return hmac.compare_digest(password, password_hash)

    if algorithm != PASSWORD_HASH_PREFIX:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        int(iterations_text),
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def _write_credentials(payload):
    ADMIN_CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def verify_admin_password(password, credentials):
    return verify_password(password, credentials.get("password_hash", ""))


def mask_email(email):
    email = str(email or "").strip()
    if "@" not in email:
        return ""
    local_part, domain = email.split("@", 1)
    if len(local_part) <= 2:
        visible_local = local_part[:1]
    else:
        visible_local = f"{local_part[:2]}{'*' * max(len(local_part) - 2, 1)}"
    return f"{visible_local}@{domain}"


def load_admin_credentials():
    env_username = os.environ.get("LIBRARY_ADMIN_USERNAME", "").strip()
    env_password = os.environ.get("LIBRARY_ADMIN_PASSWORD", "")
    env_email = os.environ.get("LIBRARY_ADMIN_EMAIL", "").strip()
    if env_username and env_password:
        return {
            "username": env_username,
            "password_hash": hash_password(env_password),
            "email": env_email,
        }

    default_credentials = _default_credentials()

    if not ADMIN_CONFIG_FILE.exists():
        return _write_credentials(default_credentials)

    try:
        config = json.loads(ADMIN_CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _write_credentials(default_credentials)

    username = str(config.get("username", "")).strip()
    email = str(config.get("email", default_credentials["email"])).strip()
    password_hash = str(config.get("password_hash", "")).strip()
    legacy_password = str(config.get("password", ""))

    if not username:
        return _write_credentials(default_credentials)

    if password_hash:
        normalized = {
            "username": username,
            "password_hash": password_hash,
            "email": email,
        }
        if normalized != config:
            return _write_credentials(normalized)
        return normalized

    if legacy_password:
        return _write_credentials(
            {
                "username": username,
                "password_hash": hash_password(legacy_password),
                "email": email,
            }
        )

    return _write_credentials(default_credentials)


def create_session(username):
    session_id = secrets.token_urlsafe(24)
    SESSIONS[session_id] = {
        "username": username,
        "expires_at": datetime.now() + SESSION_TIMEOUT,
    }
    return session_id


def remove_session(session_id):
    if session_id:
        SESSIONS.pop(session_id, None)


def is_authenticated(session_id):
    if not session_id:
        return False

    session = SESSIONS.get(session_id)
    if not session:
        return False

    if datetime.now() > session["expires_at"]:
        SESSIONS.pop(session_id, None)
        return False

    return True


def save_admin_credentials(username, password, email):
    payload = {
        "username": username,
        "password_hash": hash_password(password),
        "email": email,
    }
    return _write_credentials(payload)


def create_password_reset_otp():
    return f"{secrets.randbelow(1000000):06d}"


def store_password_reset_otp(username, code):
    PASSWORD_RESET_OTP[username] = {
        "code": code,
        "expires_at": datetime.now() + timedelta(minutes=10),
    }


def verify_password_reset_otp(username, code):
    otp_data = PASSWORD_RESET_OTP.get(username)
    if not otp_data:
        return False, "No OTP request found for this username."
    if datetime.now() > otp_data["expires_at"]:
        PASSWORD_RESET_OTP.pop(username, None)
        return False, "OTP expired. Please request a new one."
    if str(code).strip() != otp_data["code"]:
        return False, "Invalid OTP."
    return True, ""


def clear_password_reset_otp(username):
    PASSWORD_RESET_OTP.pop(username, None)
