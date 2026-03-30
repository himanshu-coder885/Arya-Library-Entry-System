import os
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
RUNTIME_DATA_DIR = BASE_DIR

if os.environ.get("VERCEL"):
    RUNTIME_DATA_DIR = Path("/tmp/qr_scanner_system")
    RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_STUDENTS_FILE = BASE_DIR / "students.csv"
LIBRARY_DATA_FILE = BASE_DIR / "library_management - Sheet1 (2).csv"
EXCEL_STUDENTS_FILE = BASE_DIR / "ACE DATA-2024-25. Librar.xlsx"
ROOT_VISITS_FILE = BASE_DIR / "visits.csv"
ROOT_ADMIN_CONFIG_FILE = BASE_DIR / "admin_config.json"
ROOT_EMAIL_CONFIG_FILE = BASE_DIR / "email_config.json"
ROOT_LIBRARY_DB_FILE = BASE_DIR / "library_data.db"

VISITS_FILE = RUNTIME_DATA_DIR / "visits.csv"
ADMIN_CONFIG_FILE = RUNTIME_DATA_DIR / "admin_config.json"
EMAIL_CONFIG_FILE = RUNTIME_DATA_DIR / "email_config.json"
LIBRARY_DB_FILE = RUNTIME_DATA_DIR / "library_data.db"

WINDOW_NAME = "Library Management Scanner"
COOLDOWN_SECONDS = 2
DUPLICATE_SCAN_GAP_SECONDS = 8

VISIT_FIELDS = [
    "visit_id",
    "student_id",
    "name",
    "father_name",
    "date",
    "entry_time",
    "exit_time",
]

HOST = "127.0.0.1"
PORT = 8000

HTML_FILE = DASHBOARD_DIR / "index.html"
LOGIN_HTML_FILE = DASHBOARD_DIR / "login.html"
CAMERA_HTML_FILE = DASHBOARD_DIR / "camera.html"
RECENT_VISITS_HTML_FILE = DASHBOARD_DIR / "recent_visits.html"
STUDENTS_INSIDE_HTML_FILE = DASHBOARD_DIR / "students_inside.html"
WEEKLY_REPORT_HTML_FILE = DASHBOARD_DIR / "weekly_report.html"
CSS_FILE = DASHBOARD_DIR / "styles.css"
JS_FILE = DASHBOARD_DIR / "app.js"
LOGIN_CSS_FILE = DASHBOARD_DIR / "login.css"
LOGIN_JS_FILE = DASHBOARD_DIR / "login.js"
FAVICON_FILE = DASHBOARD_DIR / "favicon.svg"
ARYA_LOGO_FILE = DASHBOARD_DIR / "arya_logo.svg"
ACE_LOGO_FILE = BASE_DIR / "ACE LOGO.jpg.jpeg"


def _seed_runtime_file(source: Path, destination: Path, default_text: str = ""):
    if destination.exists():
        return
    if source.exists():
        shutil.copy2(source, destination)
        return
    destination.write_text(default_text, encoding="utf-8")


if os.environ.get("VERCEL"):
    _seed_runtime_file(ROOT_VISITS_FILE, VISITS_FILE, "visit_id,student_id,name,father_name,date,entry_time,exit_time\n")
    _seed_runtime_file(ROOT_ADMIN_CONFIG_FILE, ADMIN_CONFIG_FILE, '{\n  "username": "admin",\n  "password": "ChangeMe123!",\n  "email": ""\n}\n')
    _seed_runtime_file(ROOT_EMAIL_CONFIG_FILE, EMAIL_CONFIG_FILE, '{\n  "smtp_host": "smtp.gmail.com",\n  "smtp_port": 587,\n  "sender_email": "",\n  "sender_name": "Arya Central Library",\n  "sender_password": "",\n  "use_tls": true\n}\n')
    if ROOT_LIBRARY_DB_FILE.exists() and not LIBRARY_DB_FILE.exists():
        shutil.copy2(ROOT_LIBRARY_DB_FILE, LIBRARY_DB_FILE)
