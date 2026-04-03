from datetime import datetime

from library_app.config import (
    DEFAULT_STUDENTS_FILE,
    DUPLICATE_SCAN_GAP_SECONDS,
    EXCEL_STUDENTS_FILE,
    LIBRARY_DATA_FILE,
    VISIT_FIELDS,
    VISITS_FILE,
)
from library_app.database import create_visit, ensure_database_ready, fetch_students, fetch_visits, update_visit_exit


def get_students_file():
    if EXCEL_STUDENTS_FILE.exists():
        return EXCEL_STUDENTS_FILE
    if LIBRARY_DATA_FILE.exists():
        return LIBRARY_DATA_FILE
    return DEFAULT_STUDENTS_FILE


def ensure_students_file():
    ensure_database_ready()


def ensure_visits_file():
    ensure_database_ready()


def load_students():
    return fetch_students()


def load_visits():
    return fetch_visits()


def save_visits(visits):
    import csv

    with VISITS_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=VISIT_FIELDS)
        writer.writeheader()
        writer.writerows(visits)
    return visits


def is_membership_valid(student):
    valid_until = student.get("valid_until", "").strip()
    if not valid_until:
        return True, ""

    try:
        expiry_date = datetime.strptime(valid_until, "%Y-%m-%d").date()
    except ValueError:
        return False, "Student date format invalid"

    today = datetime.now().date()
    if today > expiry_date:
        return False, f"ID expired on {expiry_date.isoformat()}"

    return True, ""


def find_open_visit(visits, student_id, visit_date):
    for visit in reversed(visits):
        if (
            visit["student_id"] == student_id
            and visit["date"] == visit_date
            and not visit["exit_time"].strip()
        ):
            return visit
    return None


def parse_timestamp(date_text, time_text):
    if not date_text or not time_text:
        return None
    try:
        return datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def get_last_scan_timestamp(visits, student_id):
    for visit in reversed(visits):
        if visit["student_id"] != student_id:
            continue
        exit_timestamp = parse_timestamp(visit["date"], visit["exit_time"])
        if exit_timestamp is not None:
            return exit_timestamp
        entry_timestamp = parse_timestamp(visit["date"], visit["entry_time"])
        if entry_timestamp is not None:
            return entry_timestamp
    return None


def process_scan_result(student_id):
    student_id = str(student_id).strip()
    students = load_students()
    visits = load_visits()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    if student_id not in students:
        return {
            "ok": False,
            "message": f"Student ID not found: {student_id}",
            "student": None,
            "visit": None,
            "action": "not_found",
        }

    student = students[student_id]
    is_valid, reason = is_membership_valid(student)
    if not is_valid:
        return {
            "ok": False,
            "message": reason,
            "student": student,
            "visit": None,
            "action": "invalid",
        }

    last_scan_timestamp = get_last_scan_timestamp(visits, student_id)
    if last_scan_timestamp is not None:
        elapsed = (now - last_scan_timestamp).total_seconds()
        if elapsed < DUPLICATE_SCAN_GAP_SECONDS:
            return {
                "ok": False,
                "message": f"Duplicate scan ignored. Try again after {int(DUPLICATE_SCAN_GAP_SECONDS - elapsed) + 1} seconds.",
                "student": student,
                "visit": None,
                "action": "duplicate",
            }

    open_visit = find_open_visit(visits, student_id, today)

    if open_visit is None:
        visit = create_visit(student)
        save_visits(load_visits())
        return {
            "ok": True,
            "message": f"Entry saved: {student['name']} ({student['student_id']})",
            "student": student,
            "visit": visit,
            "action": "entry",
        }

    open_visit = update_visit_exit(student_id, today)
    if open_visit is None:
        return {
            "ok": False,
            "message": "Could not update the existing visit. Please try again.",
            "student": student,
            "visit": None,
            "action": "error",
        }
    save_visits(load_visits())
    return {
        "ok": True,
        "message": f"Exit saved: {student['name']} ({student['student_id']})",
        "student": student,
        "visit": open_visit,
        "action": "exit",
    }


def process_scan(student_id):
    result = process_scan_result(student_id)
    return result["ok"], result["message"]


def get_recent_visits(limit=10):
    visits = load_visits()
    recent = list(reversed(visits))
    if limit is not None:
        return recent[:limit]
    return recent


def get_active_visits():
    today = datetime.now().strftime("%Y-%m-%d")
    return [visit for visit in load_visits() if visit["date"] == today and not visit["exit_time"].strip()]


def get_dashboard_summary():
    students = load_students()
    visits = load_visits()
    today = datetime.now().strftime("%Y-%m-%d")
    active_visits = [visit for visit in visits if visit["date"] == today and not visit["exit_time"].strip()]
    today_visits = [visit for visit in visits if visit["date"] == today]

    return {
        "student_count": len(students),
        "total_visits": len(visits),
        "today_visits": len(today_visits),
        "inside_count": len(active_visits),
        "today": today,
    }
