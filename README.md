## Medi Vision AI

Medi Vision AI is a full-stack, AI-powered medical shop ERP for billing, inventory management, customer CRM, face recognition, and automated reordering. It combines a Flask backend with a SQLite database and a web dashboard to help manage day-to-day pharmacy operations from one place.

### Features

- Billing and invoice management
- Medicine inventory tracking
- Shelf mapping for medicine locations
- Customer and supplier CRM
- Doctor records
- Face recognition support for customer handling
- Reorder alerts and stock monitoring

### Setup

1. Create and activate a Python virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install the dependencies:

```bash
pip install -r requirements.txt
```

3. Start the application:

```bash
python run.py
```

4. Open the app in your browser:

```text
http://127.0.0.1:5001
```

### Project Structure

- `run.py` is the local development entrypoint.
- `wsgi.py` is the production entrypoint.
- `backend/app_factory.py` builds the Flask app and registers routes.
- `backend/db.py` holds database setup, migrations, and shared row helpers.
- `backend/routes/` contains the route groups split by feature area.
- `frontend/templates/dashboard.html` is the main UI entrypoint served at `/`.
- `frontend/static/` holds the browser assets used by the dashboard.

### Notes

- The app uses SQLite by default and creates `database.db` in the project folder.
- You can set `PHARMACY_DB_PATH` if you want to use a different database location.
