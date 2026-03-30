# Library Management Scanner

This project scans a student barcode or QR code, matches the student in a local file, saves entry time, and updates exit time on the next scan.

## Files

- `library_management_system.py`: main scanner app
- `students.csv`: local student database
- `visits.csv`: visit log file created automatically

## How it works

1. Student barcode value must match `student_id` in `students.csv`.
2. If the student's ID is valid and no open visit exists, the system creates a new row with entry time.
3. If the student already has an open visit, the next scan fills the exit time in the same row.
4. After exit is saved, the next visit creates a new row again.

## Run scanner in VS Code terminal

```powershell
pip install -r scanner_requirements.txt
python library_management_system.py
```

## Run web dashboard

Use the local web UI for front-desk display:

```powershell
& 'C:\Users\A\AppData\Local\Programs\Python\Python313\python.exe' .\web_dashboard.py
```

Then open:

```text
http://127.0.0.1:8000
```

Or just double-click:

```text
start_dashboard.bat
```

## Librarian login

The admin login for the dashboard is stored in:

```text
admin_config.json
```

Current format:

```json
{
  "username": "himanshuprajapat",
  "password": "Himan@12345",
  "email": "hp81790@gmail.com"
}
```

If you want to change the admin panel login later:

1. Open `admin_config.json`
2. Edit the username or password
3. Save the file
4. Restart `web_dashboard.py`

## Forgot password email setup

The login page can send a password recovery request automatically to the admin email.

Email sender settings are stored in:

```text
email_config.json
```

Fill these values before using automatic email sending:

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "sender_email": "yourgmail@gmail.com",
  "sender_name": "Arya Central Library",
  "sender_password": "your-gmail-app-password",
  "use_tls": true
}
```

For Gmail, use an App Password, not your normal Gmail password.

## Vercel deployment note

This project now includes:

- `api/index.py`
- `vercel.json`

These files let Vercel route all requests into the Python handler.

Important:

- On Vercel, writable runtime files use temporary storage
- Dashboard pages can open there
- Persistent visit logging and config updates are not guaranteed across cold starts without an external database

## Student data format

Use this column format in `students.csv`:

```csv
student_id,name,course,phone,valid_until
LIB001,Rahul Kumar,BCA,9876543210,2026-12-31
```

`valid_until` must be in `YYYY-MM-DD` format.
