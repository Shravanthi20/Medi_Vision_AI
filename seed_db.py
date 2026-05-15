from backend.app_factory import create_app
from backend.extensions import db
from backend.models.core import Role, User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Seed roles if they don't exist
    role_names = ["admin", "manager", "staff", "junior"]
    for rn in role_names:
        if not Role.query.filter_by(role_name=rn).first():
            db.session.add(Role(role_name=rn))
    db.session.commit()

    # Ensure roles exist (mapping 'staff' to 'user' and 'junior staff' to 'junior')
    roles_map = {
        "admin": Role.query.filter_by(role_name="admin").first(),
        "manager": Role.query.filter_by(role_name="manager").first(),
        "staff": Role.query.filter_by(role_name="staff").first(),
        "junior staff": Role.query.filter_by(role_name="junior").first()
    }
    users_to_add = [
        {"name": "System Administrator", "username": "admin", "phone": "-", "code": "1", "role": "admin"},
    ]

    for u_data in users_to_add:
        user = User.query.filter_by(username=u_data["username"]).first()
        role = roles_map.get(u_data["role"])
        
        if not role:
            print(f"Error: Role {u_data['role']} not found for user {u_data['username']}")
            continue

        if user:
            # Update existing user
            user.password_hash = generate_password_hash(u_data["username"])
            user.role_id = role.role_id
            user.name = u_data["name"]
            user.phone = u_data["phone"]
            user.machine_code = u_data["code"]
            print(f"Updated user: {u_data['username']}")
        else:
            # Create new user
            new_user = User(
                username=u_data["username"],
                name=u_data["name"],
                phone=u_data["phone"],
                password_hash=generate_password_hash(u_data["username"]),
                role_id=role.role_id,
                machine_code=u_data["code"],
                is_super_admin=(u_data["role"] == "admin"),
                is_active=True
            )
            db.session.add(new_user)
            print(f"Created user: {u_data['username']}")
    
    db.session.commit()
    print("\nAll users have been synchronized successfully!")
