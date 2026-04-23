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
7. Create user groups

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
