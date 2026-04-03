import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import api.index as api_index
import library_app.auth as auth
import library_app.config as config
import library_app.data_store as data_store
import library_app.database as database


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

        auth.SESSIONS.clear()
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

        with patch.object(data_store, "DUPLICATE_SCAN_GAP_SECONDS", 1):
            first = self.client.post("/api/scan", json={"student_id": "LIB001"})
            second = self.client.post("/api/scan", json={"student_id": "LIB001"})
            time.sleep(1.1)
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


if __name__ == "__main__":
    unittest.main()
