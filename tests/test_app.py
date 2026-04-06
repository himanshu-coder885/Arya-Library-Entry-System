import json
import os
import sys
import tempfile
import time
import types
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import api.index as api_index
import library_app.auth as auth
import library_app.config as config
import library_app.data_store as data_store
import library_app.database as database


class FakePsycopgCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, query, params=()):
        self.connection.executed.append((query, params))
        if "RETURNING visit_id" in query:
            self.rows = [{"visit_id": 11}]
        elif "SELECT COUNT(*) AS total FROM students" in query:
            self.rows = [{"total": 0}]
        elif "SELECT COUNT(*) AS total FROM visits" in query:
            self.rows = [{"total": 0}]
        elif "SELECT value FROM sync_state" in query:
            self.rows = []
        else:
            self.rows = []

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakePsycopgConnection:
    def __init__(self):
        self.executed = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return FakePsycopgCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class LibraryAppTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.admin_config = self.root / "admin_config.json"
        self.email_config = self.root / "email_config.json"
        self.students_file = self.root / "students.csv"
        self.visits_file = self.root / "visits.csv"
        self.db_file = self.root / "library_data.db"
        self.excel_file = self.root / "students.xlsx"
        self.library_csv = self.root / "library_data.csv"

        self.students_file.write_text(
            "student_id,name,father_name,course,phone,valid_until\n"
            "LIB001,Test Student,Test Father,BCA,9999999999,\n",
            encoding="utf-8",
        )
        self.visits_file.write_text(
            "visit_id,student_id,name,father_name,date,entry_time,exit_time\n",
            encoding="utf-8",
        )
        self.admin_config.write_text(
            json.dumps(
                {
                    "username": "adminuser",
                    "password": "Secret123",
                    "email": "admin@example.com",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.email_config.write_text(
            json.dumps(
                {
                    "smtp_host": "smtp.gmail.com",
                    "smtp_port": 587,
                    "sender_email": "",
                    "sender_name": "Arya Library Dashboard",
                    "sender_password": "",
                    "use_tls": True,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        self.patches = [
            patch.object(auth, "ADMIN_CONFIG_FILE", self.admin_config),
            patch.object(config, "ADMIN_CONFIG_FILE", self.admin_config),
            patch.object(config, "EMAIL_CONFIG_FILE", self.email_config),
            patch.object(config, "VISITS_FILE", self.visits_file),
            patch.object(config, "LIBRARY_DB_FILE", self.db_file),
            patch.object(database, "BASE_DIR", self.root),
            patch.object(database, "DEFAULT_STUDENTS_FILE", self.students_file),
            patch.object(database, "EXCEL_STUDENTS_FILE", self.excel_file),
            patch.object(database, "LIBRARY_DATA_FILE", self.library_csv),
            patch.object(database, "LIBRARY_DB_FILE", self.db_file),
            patch.object(database, "VISITS_FILE", self.visits_file),
            patch.object(data_store, "DEFAULT_STUDENTS_FILE", self.students_file),
            patch.object(data_store, "EXCEL_STUDENTS_FILE", self.excel_file),
            patch.object(data_store, "LIBRARY_DATA_FILE", self.library_csv),
            patch.object(data_store, "VISITS_FILE", self.visits_file),
        ]

        for active_patch in self.patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)

        auth.PASSWORD_RESET_OTP.clear()
        self.client = api_index.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_plaintext_admin_password_is_migrated(self):
        credentials = auth.load_admin_credentials()

        self.assertIn("password_hash", credentials)
        self.assertTrue(auth.verify_admin_password("Secret123", credentials))

        saved = json.loads(self.admin_config.read_text(encoding="utf-8"))
        self.assertIn("password_hash", saved)
        self.assertNotIn("password", saved)

    def test_scan_flow_records_entry_duplicate_then_exit(self):
        login_response = self.client.post(
            "/api/login",
            json={"username": "adminuser", "password": "Secret123"},
        )
        self.assertEqual(login_response.status_code, 200)

        with patch.object(data_store, "DUPLICATE_SCAN_GAP_SECONDS", 3):
            first = self.client.post("/api/scan", json={"student_id": "LIB001"})
            second = self.client.post("/api/scan", json={"student_id": "LIB001"})
            time.sleep(3.1)
            third = self.client.post("/api/scan", json={"student_id": "LIB001"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json["action"], "entry")
        self.assertEqual(second.json["action"], "duplicate")
        self.assertEqual(third.json["action"], "exit")

        visits = self.visits_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(visits), 2)
        self.assertIn("LIB001", visits[1])
        self.assertRegex(visits[1], r",\d{2}:\d{2}:\d{2}$")

    def test_failed_forgot_password_does_not_store_otp(self):
        with patch.object(api_index, "send_password_recovery_email", return_value=(False, "SMTP unavailable")):
            response = self.client.post(
                "/api/forgot-password",
                json={"username": "adminuser"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(auth.PASSWORD_RESET_OTP)
        self.assertEqual(response.json["admin_email"], "ad***@example.com")

    def test_session_token_is_stateless(self):
        login_response = self.client.post(
            "/api/login",
            json={"username": "adminuser", "password": "Secret123"},
        )

        self.assertEqual(login_response.status_code, 200)
        session_cookie = login_response.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
        self.assertTrue(auth.is_authenticated(session_cookie))

    def test_session_token_stays_valid_with_env_credentials(self):
        with (
            patch.dict(
                "os.environ",
                {
                    "LIBRARY_ADMIN_USERNAME": "envadmin",
                    "LIBRARY_ADMIN_PASSWORD": "EnvSecret123",
                    "LIBRARY_ADMIN_EMAIL": "envadmin@example.com",
                },
                clear=False,
            ),
        ):
            client = api_index.app.test_client()
            login_response = client.post(
                "/api/login",
                json={"username": "envadmin", "password": "EnvSecret123"},
            )

            self.assertEqual(login_response.status_code, 200)
            session_cookie = login_response.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
            self.assertTrue(auth.is_authenticated(session_cookie))

    def test_postgres_mode_uses_database_url_and_postgres_queries(self):
        fake_connection = FakePsycopgConnection()
        fake_psycopg = types.SimpleNamespace(connect=lambda *args, **kwargs: fake_connection)
        fake_rows = types.SimpleNamespace(dict_row=object())

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://example"}, clear=False),
            patch.dict(sys.modules, {"psycopg": fake_psycopg, "psycopg.rows": fake_rows}),
        ):
            database.initialize_database()
            visit = database.create_visit(
                {
                    "student_id": "LIB001",
                    "name": "Test Student",
                    "father_name": "Test Father",
                }
            )

        self.assertEqual(visit["visit_id"], "00011")
        executed_queries = "\n".join(query for query, _ in fake_connection.executed)
        self.assertIn("CREATE TABLE IF NOT EXISTS students", executed_queries)
        self.assertIn("CREATE TABLE IF NOT EXISTS visits", executed_queries)
        self.assertIn("%s", executed_queries)
        self.assertTrue(fake_connection.committed)
        self.assertTrue(fake_connection.closed)

    def test_future_last_scan_timestamp_does_not_trigger_broken_duplicate_message(self):
        future_timestamp = data_store.datetime.now() + timedelta(hours=5, minutes=7)

        with (
            patch.object(
                data_store,
                "load_students",
                return_value={
                    "LIB001": {
                        "student_id": "LIB001",
                        "name": "Test Student",
                        "father_name": "Test Father",
                        "course": "BCA",
                        "phone": "",
                        "valid_until": "",
                    }
                },
            ),
            patch.object(data_store, "load_visits", return_value=[]),
            patch.object(data_store, "get_last_scan_timestamp", return_value=future_timestamp),
            patch.object(
                data_store,
                "create_visit",
                return_value={
                    "visit_id": "00001",
                    "student_id": "LIB001",
                    "name": "Test Student",
                    "father_name": "Test Father",
                    "date": "2026-04-06",
                    "entry_time": "10:00:00",
                    "exit_time": "",
                },
            ),
            patch.object(data_store, "save_visits"),
        ):
            result = data_store.process_scan_result("LIB001")

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "entry")


if __name__ == "__main__":
    unittest.main()
