## Selvam Medicals — Smart AI Pharma ERP System (Auth Module)

This is the consolidated Backend Authentication module for the Selvam Medicals AI Pharma ERP system.

### Features
- **FastAPI / SQLAlchemy**: Modern, high-performance asynchronous stack.
- **PostgreSQL Support**: Production-ready database schema using SQLAlchemy models.
- **JWT Authentication**: Secure login, refresh token rotation, and logout functionality.
- **RBAC (Role-Based Access Control)**: Granular permissions and automated security guards.
- **Security**: Direct `bcrypt` password hashing.

### Setup

1. **Environment Configuration**:
   The application reads from the `.env` file. Ensure `DATABASE_URL` is set to your PostgreSQL instance.

2. **Run with Docker**:
   ```bash
   docker-compose up -d
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the Application**:
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Interactive API Docs**:
   Navigate to [http://localhost:8000/docs](http://localhost:8000/docs) to test the endpoints.

### Project Structure
- `app/`: Core application package.
  - `auth/`: Authentication module (routes, schemas, dependencies, utils).
  - `main.py`: Application entry point.
  - `models.py`: Database models.
  - `database.py`: Database connection setup.
- `static/`: Static assets for Face-API.
- `docker-compose.yml`: PostgreSQL container definition.
- `.env`: Environment variables.
