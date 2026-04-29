# Pharma Project Setup and API Guide

## Overview

This project is a Django + Django REST Framework clinic system.

Recent appointment workflow additions:

- `ConsultationRecord` is now linked to `appointments.Appointment`
- appointments support the statuses `pending`, `confirmed`, `declined`, `checked_in`, `completed`, `no_show`, and `cancelled`
- checked-in appointments create or update a consultation record with `check_in_time`
- doctors can view a daily checked-in queue ordered by check-in time
- appointments can be filtered, analyzed, and exported as CSV

## 1. Clone the Repository

```bash
git clone <REPO_LINK>
cd <PROJECT_FOLDER_NAME>
```

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

If activation works, you should see `(venv)` in the terminal.

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Important: this project uses Django REST Framework. If it is not already listed in `requirements.txt` or installed in your environment, install it manually:

```bash
pip install djangorestframework
```

If `requirements.txt` does not exist yet, install the core packages manually:

```bash
pip install django djangorestframework
```

## 4. Apply Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

If `python` does not work on your machine, use `python3` instead.

This creates the local SQLite database and project tables.

## 5. Create a Superuser

```bash
python manage.py createsuperuser
```

Enter:

- username
- email
- password

This account can access the Django admin panel if needed.

## 6. Run the Server

```bash
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/
```

## 7. Create User Groups

Open Django shell:

```bash
python manage.py shell
```

Then run:

```python
from django.contrib.auth.models import Group

Group.objects.get_or_create(name="Patient")
Group.objects.get_or_create(name="Doctor")
Group.objects.get_or_create(name="Receptionist")
Group.objects.get_or_create(name="Admin")
```

Then exit the shell:

```python
exit()
```

These groups are required for role-based access.

## 8. Notes About Auth for Current APIs

- Current API protection uses standard DRF `IsAuthenticated`
- full custom auth and permission rules are still pending
- for API testing, log in first through the browser so Django session auth works

## 9. Postman / Session Authentication Setup

The appointments and consultations APIs currently use Django session authentication.

1. Log in through:
   `http://127.0.0.1:8000/accounts/login/`
2. Copy the `sessionid` cookie into Postman
3. For `POST`, `PUT`, `PATCH`, and `DELETE` requests, also send:
   - the `csrftoken` cookie
   - the header `X-CSRFToken: <csrftoken>`
4. Use `Accept: application/json` on API requests
5. For JSON requests, also send `Content-Type: application/json`

If Postman does not already have a `csrftoken` cookie, first send a `GET` request to one of these URLs:

- `http://127.0.0.1:8000/accounts/login/`
- `http://127.0.0.1:8000/appointments/api/`
- `http://127.0.0.1:8000/consultations/`

If Postman still reports a CSRF error, make sure the request includes the `csrftoken` cookie itself, not only the `X-CSRFToken` header. The header and cookie must match.

## 10. Appointment and Consultation Workflow

The current flow is:

1. Book an appointment
2. Check in the patient on the appointment day
3. A `ConsultationRecord` is created or updated for that appointment
4. The doctor sees checked-in patients in the daily queue
5. The appointment can later be marked `completed` or `no_show`

`ConsultationRecord` now includes:

- `appointment`: `OneToOneField` to `appointments.Appointment`
- `check_in_time`: timestamp set during patient check-in
- `notes`
- `diagnosis`
- `requested_tests`
- nested `prescriptions`

## 11. Appointments API

Base URL:

```text
http://127.0.0.1:8000/appointments/api/
```

### API Root

- Method: `GET`
- URL: `/appointments/api/`
- Returns the main appointment API links

### List Doctors

- Method: `GET`
- URL: `/appointments/api/doctors/`
- Response: `{"doctors": [...]}`

### View Doctor Slots

- Method: `GET`
- URL: `/appointments/api/doctors/<doctor_id>/?date=YYYY-MM-DD`
- Example:

```text
http://127.0.0.1:8000/appointments/api/doctors/1/?date=2026-05-01
```

### Book Appointment

- Method: `POST`
- URL: `/appointments/api/doctors/<doctor_id>/book/`
- Body:

```json
{
  "date": "2026-05-01",
  "start_time": "09:00:00",
  "end_time": "09:30:00"
}
```

### Patient Appointments

- Method: `GET`
- URL: `/appointments/api/appointments/`
- Response shape:

```json
{
  "upcoming": [],
  "past": [],
  "cancelled": []
}
```

### Reschedule Appointment

- Method: `POST`
- URL: `/appointments/api/appointments/<appointment_id>/reschedule/`
- Body:

```json
{
  "date": "2026-05-02",
  "start_time": "10:00:00",
  "end_time": "10:30:00"
}
```

### Cancel Appointment

- Method: `POST`
- URL: `/appointments/api/appointments/<appointment_id>/cancel/`
- Body: none

### Check In Appointment

- Method: `POST`
- URL: `/appointments/api/appointments/<appointment_id>/check-in/`
- Body: none
- Behavior:
  - sets appointment status to `checked_in`
  - creates or updates the linked consultation record
  - stores the current `check_in_time`

### Doctor Daily Queue

- Method: `GET`
- URL: `/appointments/api/doctors/<doctor_id>/queue/`
- Behavior:
  - filters appointments for today
  - only includes `checked_in` appointments
  - orders by `consultation_record.check_in_time`
  - includes calculated `waiting_time`

### Update Appointment Status

- Method: `POST`
- URL: `/appointments/api/appointments/<appointment_id>/status/`
- Allowed values:
  - `completed`
  - `no_show`
- Body:

```json
{
  "status": "completed"
}
```

Rules:

- `completed` requires an existing consultation record
- `no_show` is blocked for future appointments
- `no_show` is blocked if a consultation record already exists

### Search and Filter Appointments

- Method: `GET`
- URL: `/appointments/api/appointments/search/`
- Supported query params:
  - `id`
  - `appointment_id`
  - `doctor_id`
  - `patient_name`
  - `status`
  - `start_date`
  - `end_date`

Example:

```text
/appointments/api/appointments/search/?patient_name=omar&status=checked_in&start_date=2026-05-01&end_date=2026-05-31
```

### Admin Analytics

- Method: `GET`
- URL: `/appointments/api/admin/analytics/`
- Calculates:
  - total appointments
  - no-show count
  - no-show rate
  - peak hours grouped by appointment `start_time`

This endpoint also supports the same filters as the search endpoint.

### CSV Export

- Method: `GET`
- URL: `/appointments/api/appointments/export/csv/`
- Returns a CSV download of the filtered appointment list

This endpoint supports the same filters as the search endpoint.

## 12. Consultations API

Base URL:

```text
http://127.0.0.1:8000/consultations/
```

### List Consultation Records

- Method: `GET`
- URL: `/consultations/`

### Create Consultation Record

- Method: `POST`
- URL: `/consultations/`
- Body example:

```json
{
  "appointment": 1,
  "check_in_time": "2026-05-01T09:10:00Z",
  "notes": "Patient reports headache.",
  "diagnosis": "Migraine",
  "requested_tests": "CBC",
  "prescriptions": [
    {
      "drug": "Paracetamol",
      "dose": "1 tablet every 8 hours",
      "duration": "5 days"
    }
  ]
}
```

### Retrieve Consultation Record

- Method: `GET`
- URL: `/consultations/<id>/`

### Update Consultation Record

- Method: `PUT` or `PATCH`
- URL: `/consultations/<id>/`

### Delete Consultation Record

- Method: `DELETE`
- URL: `/consultations/<id>/`

## 13. Important Development Notes

- The project database is SQLite by default
- Some local environments may require `python3` instead of `python`
- The repository currently ignores migration files with the rule `*/migrations/*`
- Because of that rule, teammates may need to run `makemigrations` locally before `migrate`
- The new appointment and consultation schema changes depend on those migrations being generated/applied locally if they are not committed

## 14. Suggested API Testing Order

1. Log in from the browser
2. Call `/appointments/api/doctors/`
3. Call `/appointments/api/doctors/<doctor_id>/?date=YYYY-MM-DD`
4. Book with `/appointments/api/doctors/<doctor_id>/book/`
5. View `/appointments/api/appointments/`
6. Check in with `/appointments/api/appointments/<appointment_id>/check-in/`
7. View the doctor queue at `/appointments/api/doctors/<doctor_id>/queue/`
8. Update status with `/appointments/api/appointments/<appointment_id>/status/`
9. Use search, analytics, or CSV export as needed
