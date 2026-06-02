import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from backend.app_factory import create_app
from backend.extensions import db
from backend.models.core import User, Role

app = create_app()
with app.app_context():
    user = User.query.filter_by(username='admin').first()
    if user:
        print(f"User: {user.username}, Role ID: {user.role_id}")
        role = Role.query.get(user.role_id)
        print(f"Role Name: {role.role_name}")
