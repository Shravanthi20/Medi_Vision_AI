from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from .config import STATIC_DIR, TEMPLATES_DIR
from .db import init_db
from .routes import register_blueprints


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(TEMPLATES_DIR),
        static_folder=str(STATIC_DIR),
        static_url_path="/static",
    )
    CORS(app)
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
    register_blueprints(app)
    init_db()
    return app
