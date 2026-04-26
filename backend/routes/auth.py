from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from functools import wraps
from werkzeug.security import check_password_hash
from ..db import get_conn

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
                return redirect(url_for("core.dashboard")) # redirect to dashboard if not enough permissions
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

    with get_conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE LOWER(username) = ? AND is_active = 1", (username.lower(),)).fetchone()
        
    if user and check_password_hash(user["password_hash"], password):
        session.clear() # clear existing session to prevent session fixation
        session["logged_in"] = True
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        return jsonify({
            "status": "success", 
            "message": "Login successful",
            "user": {
                "name": user["name"],
                "role": user["role"]
            }
        })
    
    return jsonify({"status": "error", "message": "Invalid username or password"}), 401

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))
