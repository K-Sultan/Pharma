## 1. Clone the repository

git clone <REPO_LINK>
cd <PROJECT_FOLDER_NAME>



2. Create a virtual environment
On Windows
python -m venv venv
Activate it
venv\Scripts\activate

If activation works, you should see (venv) in the terminal.

3. Install dependencies
pip install -r requirements.txt

If requirements.txt does not exist yet, install Django manually:

pip install django

Then later generate requirements with:

pip freeze > requirements.txt
4. Apply migrations
python manage.py makemigrations
python manage.py migrate

This creates the local database and project tables.

5. Create a superuser
python manage.py createsuperuser

Enter:

username
email
password

This account will let you access the admin panel if needed.

6. Run the server
python manage.py runserver

Then open:

http://127.0.0.1:8000/

7. Test the appointments API in Postman

The appointments API uses a Django session, so log in through `http://127.0.0.1:8000/accounts/login/` first and copy the `sessionid` cookie into Postman. Use `Accept: application/json` on every request. For every `POST` request, you must send both cookies, `sessionid` and `csrftoken`, and add the header `X-CSRFToken: <csrftoken>`.

If Postman does not already have a `csrftoken` cookie, send a `GET` request first to `http://127.0.0.1:8000/accounts/login/` or `http://127.0.0.1:8000/appointments/api/`, then open Postman Cookie Manager for `127.0.0.1` and add the `csrftoken` value from the response cookies.

1. API root
	- Method: `GET`
	- URL: `http://127.0.0.1:8000/appointments/api/`
	- Example response: returns the doctors and patient appointments URLs

2. List all doctors
	- Method: `GET`
	- URL: `http://127.0.0.1:8000/appointments/api/doctors/`
	- Example response: `{"doctors": [...]}`

3. View a doctor's available slots for a date
	- Method: `GET`
	- URL: `http://127.0.0.1:8000/appointments/api/doctors/<doctor_id>/?date=YYYY-MM-DD`
	- Example: `http://127.0.0.1:8000/appointments/api/doctors/1/?date=2026-05-01`
	- Example response: doctor details plus `slots`

4. Book an appointment with a doctor
	- Method: `POST`
	- URL: `http://127.0.0.1:8000/appointments/api/doctors/<doctor_id>/book/`
	- Body type: `raw` JSON
	- Headers: `Accept: application/json`, `Content-Type: application/json`, `X-CSRFToken: <csrftoken>`
	- Example body:
	  ```json
	  {
		 "date": "2026-05-01",
		 "start_time": "09:00:00",
		 "end_time": "09:30:00"
	  }
	  ```

5. View your appointments
	- Method: `GET`
	- URL: `http://127.0.0.1:8000/appointments/api/appointments/`
	- Example response: `{"upcoming": [...], "past": [...], "cancelled": [...]}`

6. Reschedule an appointment
	- Method: `POST`
	- URL: `http://127.0.0.1:8000/appointments/api/appointments/<appointment_id>/reschedule/`
	- Body type: `raw` JSON
	- Headers: `Accept: application/json`, `Content-Type: application/json`, `X-CSRFToken: <csrftoken>`
	- Example body:
	  ```json
	  {
		 "date": "2026-05-02",
		 "start_time": "10:00:00",
		 "end_time": "10:30:00"
	  }
	  ```

7. Cancel an appointment
	- Method: `POST`
	- URL: `http://127.0.0.1:8000/appointments/api/appointments/<appointment_id>/cancel/`
	- Headers: `Accept: application/json`, `X-CSRFToken: <csrftoken>`
	- Body: none

If Postman still reports a CSRF error, make sure the request includes the `csrftoken` cookie itself, not only the `X-CSRFToken` header. The header and cookie must match.

Use the doctor list endpoint first to get a doctor ID, then the doctor slots endpoint to get a valid time slot, and finally the booking endpoint to create the appointment.
8. Create user groups

Open Django shell:

python manage.py shell

Then run:

from django.contrib.auth.models import Group

Group.objects.get_or_create(name='Patient')
Group.objects.get_or_create(name='Doctor')
Group.objects.get_or_create(name='Receptionist')
Group.objects.get_or_create(name='Admin')

exit()

These groups are required for role-based access.
