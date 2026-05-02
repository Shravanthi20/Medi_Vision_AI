from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func

from ..extensions import db
from ..models.core import User, Role

auth_bp = Blueprint("auth", __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("auth.login_page"))
            if session.get("role") not in roles:
                if request.is_json:
                    return jsonify({"status": "error", "message": "Access forbidden: insufficient permissions"}), 403
                return redirect(url_for("core.dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route("/login", methods=["GET"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("core.dashboard"))
    return render_template("login.html")

@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password required"}), 400

    user = db.session.query(User).join(Role).filter(
        func.lower(User.username) == username.lower(),
        User.is_active == True
    ).first()
        
    if user and check_password_hash(user.password_hash, password):
        session.clear()
        session["logged_in"] = True
        session["user_id"] = str(user.user_id)
        session["username"] = user.username
        session["name"] = user.username  # User model in main has no separate name
        session["role"] = user.role.role_name if user.role else "user"
        return jsonify({
            "status": "success", 
            "message": "Login successful",
            "user": {
                "name": user.username,
                "role": session["role"]
            }
        })
    
    return jsonify({"status": "error", "message": "Invalid username or password"}), 401

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))

@auth_bp.route("/api/users", methods=["GET"])
@role_required("admin")
def get_users():
    users = db.session.query(User).all()
    result = []
    for u in users:
        result.append({
            "id": str(u.user_id),
            "username": u.username,
            "name": u.username,
            "role": u.role.role_name if u.role else "user",
            "is_active": u.is_active
        })
    return jsonify(result)

@auth_bp.route("/api/users", methods=["POST"])
@role_required("admin")
def add_user():
    data = request.get_json() or {}
    username = data.get("username")
    role_name = data.get("role")
    password = data.get("password")
    
    if not username or not role_name:
        return jsonify({"status": "error", "message": "Username and role required"}), 400
        
    role = db.session.query(Role).filter_by(role_name=role_name).first()
    if not role:
        return jsonify({"status": "error", "message": "Invalid role"}), 400

    user_id = data.get("id")
    try:
        if user_id:
            user = db.session.query(User).filter_by(user_id=user_id).first()
            if not user:
                return jsonify({"status": "error", "message": "User not found"}), 404
            user.username = username
            user.role_id = role.role_id
            if password:
                user.password_hash = generate_password_hash(password)
            if "is_active" in data:
                user.is_active = bool(data["is_active"])
        else:
            if not password:
                return jsonify({"status": "error", "message": "Password required for new user"}), 400
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                role_id=role.role_id,
                is_active=data.get("is_active", True)
            )
            db.session.add(user)
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@auth_bp.route("/api/users/<id>", methods=["DELETE"])
@role_required("admin")
def delete_user(id):
    user = db.session.query(User).filter_by(user_id=id).first()
    if user:
        db.session.delete(user)
        db.session.commit()
    return jsonify({"status": "success"})
