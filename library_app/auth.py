import json
import secrets
from datetime import datetime, timedelta

from library_app.config import ADMIN_CONFIG_FILE


SESSIONS = {}
PASSWORD_RESET_OTP = {}


def load_admin_credentials():
    default_credentials = {
        "username": "himanshuprajapat",
        "password": "Himan@12345",
        "email": "hp81790@gmail.com",
    }

    if not ADMIN_CONFIG_FILE.exists():
        ADMIN_CONFIG_FILE.write_text(json.dumps(default_credentials, indent=2), encoding="utf-8")
        return default_credentials

    try:
        config = json.loads(ADMIN_CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_credentials

    username = str(config.get("username", "")).strip()
    password = str(config.get("password", ""))
    if not username or not password:
        return default_credentials

    return {
        "username": username,
        "password": password,
        "email": str(config.get("email", default_credentials["email"])).strip() or default_credentials["email"],
    }


def create_session(username):
    session_id = secrets.token_urlsafe(24)
    SESSIONS[session_id] = username
    return session_id


def remove_session(session_id):
    if session_id:
        SESSIONS.pop(session_id, None)


def is_authenticated(session_id):
    return bool(session_id and session_id in SESSIONS)


def save_admin_credentials(username, password, email):
    payload = {
        "username": username,
        "password": password,
        "email": email,
    }
    ADMIN_CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def create_password_reset_otp(username):
    code = f"{secrets.randbelow(1000000):06d}"
    PASSWORD_RESET_OTP[username] = {
        "code": code,
        "expires_at": datetime.now() + timedelta(minutes=10),
    }
    return code


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
