import csv
import io
import os
from datetime import datetime, timedelta

from flask import Flask, jsonify, make_response, redirect, request, send_file

from library_app.auth import (
    clear_password_reset_otp,
    create_password_reset_otp,
    create_session,
    is_authenticated,
    load_admin_credentials,
    mask_email,
    remove_session,
    save_admin_credentials,
    store_password_reset_otp,
    verify_admin_password,
    verify_password_reset_otp,
)
from library_app.config import (
    ACE_LOGO_FILE,
    ARYA_LOGO_FILE,
    CAMERA_HTML_FILE,
    CSS_FILE,
    FAVICON_FILE,
    HTML_FILE,
    JS_FILE,
    LOGIN_CSS_FILE,
    LOGIN_HTML_FILE,
    LOGIN_JS_FILE,
    RECENT_VISITS_HTML_FILE,
    STUDENTS_INSIDE_HTML_FILE,
    WEEKLY_REPORT_HTML_FILE,
)
from library_app.data_store import (
    get_active_visits,
    get_dashboard_summary,
    get_recent_visits,
    get_students_file,
    load_students,
    process_scan_result,
)
from library_app.mailer import send_password_recovery_email
from library_app.utils import read_text_file


app = Flask(__name__)


def is_logged_in():
    return is_authenticated(request.cookies.get("library_session"))


def unauthorized():
    return jsonify({"ok": False, "message": "Unauthorized"}), 401


def with_student_details(visits):
    students = load_students()
    rows = []
    for visit in visits:
        student = students.get(visit["student_id"], {})
        rows.append(
            {
                **visit,
                "course": student.get("course", visit.get("course", "")),
                "father_name": student.get("father_name", visit.get("father_name", "")),
            }
        )
    return rows


@app.get("/")
@app.get("/login")
@app.get("/login.html")
def login_page():
    if is_logged_in():
        return redirect("/admin", code=303)
    return read_text_file(LOGIN_HTML_FILE), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/admin")
@app.get("/admin/")
def admin_page():
    if not is_logged_in():
        return redirect("/", code=303)
    return read_text_file(HTML_FILE), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/camera")
@app.get("/camera/")
@app.get("/admin/camera")
def camera_page():
    if not is_logged_in():
        return redirect("/", code=303)
    return read_text_file(CAMERA_HTML_FILE), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/recent-visits")
@app.get("/recent-visits/")
def recent_visits_page():
    if not is_logged_in():
        return redirect("/", code=303)
    return read_text_file(RECENT_VISITS_HTML_FILE), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/students-inside")
@app.get("/students-inside/")
def students_inside_page():
    if not is_logged_in():
        return redirect("/", code=303)
    return read_text_file(STUDENTS_INSIDE_HTML_FILE), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/weekly-report")
@app.get("/weekly-report/")
def weekly_report_page():
    if not is_logged_in():
        return redirect("/", code=303)
    return read_text_file(WEEKLY_REPORT_HTML_FILE), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/static/styles.css")
def styles_file():
    return read_text_file(CSS_FILE), 200, {"Content-Type": "text/css; charset=utf-8"}


@app.get("/static/app.js")
def app_js_file():
    return read_text_file(JS_FILE), 200, {"Content-Type": "application/javascript; charset=utf-8"}


@app.get("/static/login.css")
def login_css_file():
    return read_text_file(LOGIN_CSS_FILE), 200, {"Content-Type": "text/css; charset=utf-8"}


@app.get("/static/login.js")
def login_js_file():
    return read_text_file(LOGIN_JS_FILE), 200, {"Content-Type": "application/javascript; charset=utf-8"}


@app.get("/static/favicon.svg")
def favicon_file():
    return read_text_file(FAVICON_FILE), 200, {"Content-Type": "image/svg+xml; charset=utf-8"}


@app.get("/static/arya_logo.svg")
def arya_logo_file():
    return read_text_file(ARYA_LOGO_FILE), 200, {"Content-Type": "image/svg+xml; charset=utf-8"}


@app.get("/static/ace_logo.jpeg")
def ace_logo_file():
    return send_file(ACE_LOGO_FILE, mimetype="image/jpeg")


@app.get("/api/dashboard")
def dashboard_api():
    if not is_logged_in():
        return unauthorized()
    today = datetime.now().strftime("%Y-%m-%d")
    recent_visits = [visit for visit in get_recent_visits(limit=None) if visit["date"] == today][:12]
    payload = {
        "summary": get_dashboard_summary(),
        "recent_visits": recent_visits,
        "recent_visits_with_students": with_student_details(recent_visits),
        "active_visits": with_student_details(get_active_visits()),
        "student_file": get_students_file().name,
    }
    return jsonify(payload)


@app.get("/api/daily-summary")
def daily_summary_api():
    if not is_logged_in():
        return unauthorized()
    visits = get_recent_visits(limit=None)
    summary_map = {}
    for visit in visits:
        row = summary_map.setdefault(
            visit["date"],
            {"date": visit["date"], "total_visits": 0, "completed_visits": 0, "inside_count": 0},
        )
        row["total_visits"] += 1
        if visit["exit_time"].strip():
            row["completed_visits"] += 1
        else:
            row["inside_count"] += 1
    return jsonify({"summary": sorted(summary_map.values(), key=lambda item: item["date"], reverse=True)})


@app.get("/api/weekly-summary")
def weekly_summary_api():
    if not is_logged_in():
        return unauthorized()
    visits = get_recent_visits(limit=None)
    summary_map = {}
    today = datetime.now().date()
    for visit in visits:
        visit_date = datetime.strptime(visit["date"], "%Y-%m-%d").date()
        iso_year, iso_week, iso_day = visit_date.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        start_date = visit_date - timedelta(days=iso_day - 1)
        end_date = start_date + timedelta(days=6)
        row = summary_map.setdefault(
            week_key,
            {
                "week_label": week_key,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_visits": 0,
                "completed_visits": 0,
                "inside_count": 0,
                "is_completed": end_date < today,
            },
        )
        row["total_visits"] += 1
        if visit["exit_time"].strip():
            row["completed_visits"] += 1
        else:
            row["inside_count"] += 1
    rows = [item for item in sorted(summary_map.values(), key=lambda item: item["week_label"], reverse=True) if item["is_completed"]]
    return jsonify({"summary": rows})


@app.get("/api/export-visits")
def export_visits_api():
    if not is_logged_in():
        return unauthorized()
    students = load_students()
    visits = get_recent_visits(limit=None)
    week_filter = request.args.get("week", "").strip()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["visit_id", "student_id", "name", "father_name", "branch", "date", "entry_time", "exit_time"])
    for visit in reversed(visits):
        if week_filter:
            visit_date = datetime.strptime(visit["date"], "%Y-%m-%d").date()
            iso_year, iso_week, _ = visit_date.isocalendar()
            if f"{iso_year}-W{iso_week:02d}" != week_filter:
                continue
        student = students.get(visit["student_id"], {})
        writer.writerow(
            [
                visit["visit_id"],
                visit["student_id"],
                visit["name"],
                student.get("father_name", visit.get("father_name", "")),
                student.get("course", visit.get("course", "")),
                visit["date"],
                visit["entry_time"],
                visit["exit_time"],
            ]
        )
    output = make_response(buffer.getvalue())
    output.headers["Content-Type"] = "text/csv; charset=utf-8"
    filename = "library_visits_report.csv" if not week_filter else f"library_visits_{week_filter}.csv"
    output.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return output


@app.post("/api/login")
def login_api():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    credentials = load_admin_credentials()
    if username != credentials["username"] or not verify_admin_password(password, credentials):
        return jsonify({"ok": False, "message": "Invalid librarian credentials."}), 401
    session_id = create_session(username)
    response = jsonify({"ok": True, "message": "Login successful."})
    response.set_cookie(
        "library_session",
        session_id,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure or bool(os.environ.get("VERCEL")),
        path="/",
    )
    return response


@app.post("/api/logout")
def logout_api():
    remove_session(request.cookies.get("library_session"))
    response = jsonify({"ok": True})
    response.delete_cookie("library_session", path="/")
    return response


@app.post("/api/forgot-password")
def forgot_password_api():
    payload = request.get_json(silent=True) or {}
    credentials = load_admin_credentials()
    requested_username = str(payload.get("username", "")).strip()
    if requested_username != credentials["username"]:
        return jsonify({"ok": False, "message": "Username does not match the admin account."}), 400
    admin_email = credentials.get("email", "")
    otp_code = create_password_reset_otp()
    ok, message = send_password_recovery_email(admin_email, requested_username, otp_code)
    if ok:
        store_password_reset_otp(requested_username, otp_code)
    return jsonify({"ok": ok, "message": message, "admin_email": mask_email(admin_email)}), (200 if ok else 400)


@app.post("/api/reset-password")
def reset_password_api():
    payload = request.get_json(silent=True) or {}
    credentials = load_admin_credentials()
    username = str(payload.get("username", "")).strip()
    otp = str(payload.get("otp", "")).strip()
    new_password = str(payload.get("new_password", ""))
    if username != credentials["username"]:
        return jsonify({"ok": False, "message": "Username does not match the admin account."}), 400
    if len(new_password) < 6:
        return jsonify({"ok": False, "message": "New password must be at least 6 characters."}), 400
    ok, message = verify_password_reset_otp(username, otp)
    if not ok:
        return jsonify({"ok": False, "message": message}), 400
    save_admin_credentials(username, new_password, credentials.get("email", ""))
    clear_password_reset_otp(username)
    return jsonify({"ok": True, "message": "Password reset successful. Please log in with the new password."})


@app.post("/api/scan")
def scan_api():
    if not is_logged_in():
        return unauthorized()
    payload = request.get_json(silent=True) or {}
    student_id = str(payload.get("student_id", "")).strip()
    if not student_id:
        return jsonify({"ok": False, "message": "Student ID is required"}), 400
    return jsonify(process_scan_result(student_id))
