from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from .config import STATIC_DIR, TEMPLATES_DIR
from .routes import register_blueprints
from .extensions import db, migrate, ma

# Import all models so Alembic auto-discovers them for migrations
from . import models  # noqa: F401

from .routes_v2 import v2_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(TEMPLATES_DIR),
        static_folder=str(STATIC_DIR),
        static_url_path="/static",
    )
    CORS(app)
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
    
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set for Postgres-only mode")

    # Configure Postgres URI
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    ma.init_app(app)

    register_blueprints(app)
    app.register_blueprint(v2_bp)

    return app
