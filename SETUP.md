# Medi Vision AI Setup Guide

This guide explains how to set up, run, and test the project in its current Postgres-first state.

## What This Project Uses Now

- Flask backend with SQLAlchemy ORM
- PostgreSQL as the required database
- Alembic/Flask-Migrate for schema management
- Bruno for API testing
- Flask templates/static assets for the dashboard UI

## Prerequisites

- Python 3.11+ recommended
- PostgreSQL 14+ recommended
- `pip` and `venv`
- Bruno installed for API testing

## Project Layout

- `run.py` - local development entrypoint
- `wsgi.py` - production entrypoint
- `backend/app_factory.py` - Flask app factory
- `backend/extensions.py` - SQLAlchemy, Migrate, Marshmallow instances
- `backend/models/` - ORM models
- `backend/routes/` - API routes
- `backend/schemas/` - Marshmallow schemas
- `frontend/templates/` - HTML templates
- `frontend/static/` - CSS, JS, models, assets
- `migrations/` - Alembic migration environment
- `bruno/` - Bruno API collection

## 1. Create a Virtual Environment

From the project root:

```bash
python -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

If you are setting up a fresh environment, make sure PostgreSQL driver and migration packages install successfully:

- `Flask-SQLAlchemy`
- `Flask-Migrate`
- `psycopg2-binary`
- `pgvector`
- `Flask-Marshmallow`
- `marshmallow-sqlalchemy`

## 3. Configure Environment Variables

Create a `.env` file in the project root.

Suggested minimum configuration:

```env
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/db
PHARMACY_STORE_NAME=Selvam Medicals
SMS_PROVIDER_MODE=auto
SMS_PROVIDER_URL=
SMS_PROVIDER_KEY=
SMS_PROVIDER_SENDER=Selvam Medicals
SMS_PROVIDER_TIMEOUT=15
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=
```

Notes:

- `DATABASE_URL` is required. The app now runs in Postgres-only mode.
- The legacy SQLite path variables are no longer used by the app.
- If you want SMS or WhatsApp integrations enabled, fill the provider credentials.

## 4. Create the PostgreSQL Database

Create a database and user if needed:

```sql
CREATE DATABASE db;
CREATE USER user_name WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE db TO user_name;
```

Make sure the `DATABASE_URL` points to that database.

## 5. Run Database Migrations

Apply the current schema to PostgreSQL:

```bash
flask db upgrade
```

If Flask does not detect the app automatically, use:

```bash
export FLASK_APP=run.py
flask db upgrade
```

For a brand-new database, this creates all ORM tables from the migration history.

## 6. Start the App

Run the development server:

```bash
python run.py
```

The app listens on:

```text
http://127.0.0.1:5001
```

## 7. Verify the Backend

Check the main health endpoints first:

- `GET /api/health`
- `GET /api/v2/health`

If those respond correctly, the app is connected to PostgreSQL and the ORM layer is working.

## 8. Test the API with Bruno

A ready-to-run Bruno collection is included in:

- `bruno/Medi_Vision_AI_API/`

Open that folder in Bruno and use the local environment:

- `bruno/Medi_Vision_AI_API/environments/local.bru`

Recommended test order:

1. Core health checks
2. Inventory list and upsert endpoints
3. Bills create/list/fetch/update/delete
4. Purchases list/create
5. Masters CRUD and customer payment
6. Communications templates and logs
7. SMS message and template endpoints

### Useful Bruno variables

The environment file includes starter IDs like:

- `billId`
- `customerId`
- `supplierId`
- `doctorId`
- `shelfId`
- `medicineId`
- `messageId`
- `templateId`
- `commTemplateId`

Update them after creating real records so follow-up requests work correctly.

## 9. Suggested Smoke Test Checklist

Run these requests after migrations:

- `GET /api/health`
- `GET /api/v2/health`
- `GET /api/medicines`
- `POST /api/medicines`
- `GET /api/shelves`
- `GET /api/bills`
- `POST /api/bills`
- `GET /api/purchases`
- `POST /api/purchases`
- `GET /api/customers`
- `POST /api/customers`
- `POST /api/customers/{id}/payment`
- `GET /api/communications/templates`
- `POST /api/communications/templates`
- `GET /api/sms/messages`
- `POST /api/sms/messages`

## 10. Common Troubleshooting

### Database connection fails

- Confirm PostgreSQL is running.
- Confirm `DATABASE_URL` is correct.
- Confirm the database user has permission to create and modify tables.

### Flask says `DATABASE_URL must be set`

- Add `DATABASE_URL` to `.env`.
- Restart the terminal or reload the environment.

### Migration errors

- Make sure the database is empty or compatible with the current migration history.
- Re-run `flask db upgrade` after fixing the connection.

### Bruno requests fail with 404

- Confirm the server is running on port `5001`.
- Check the route path in the request file.
- Verify the ID variables in the Bruno environment.

### SMS or WhatsApp requests fail

- Provider credentials may be missing.
- These integrations can still be used in local/queued mode depending on settings.

## 11. Recommended Next Steps After Setup

- Add automated API smoke tests with `pytest`
- Export or document the API contract with OpenAPI later
- Keep Bruno collection and backend routes in sync as new endpoints are added

## 12. Current Backend Status

The backend is now Postgres-first and the legacy SQLite route usage has been removed from the active API flow. The main remaining work is operational testing and any follow-up cleanup discovered during real API runs.
