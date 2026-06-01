import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
from backend.app_factory import create_app
from backend.extensions import db
import sqlalchemy

app = create_app()
with app.app_context():
    # Use sqlalchemy text explicitly
    result = db.session.execute(sqlalchemy.text(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename != 'alembic_version'"
    ))
    tables = [row[0] for row in result.fetchall()]
    if tables:
        tables_str = ", ".join(tables)
        print("Truncating:", tables_str)
        db.session.execute(sqlalchemy.text(f"TRUNCATE TABLE {tables_str} CASCADE;"))
        db.session.commit()
        print('All tables truncated successfully.')
    else:
        print('No tables found.')
