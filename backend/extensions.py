# Optional import of flask_limiter – not required for core functionality or tests
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:  # pragma: no cover
    # Minimal no‑op implementation when the library is absent
    class _DummyLimiter:
        def __init__(self, *args, **kwargs):
            pass
        def limit(self, *args, **kwargs):
            return lambda f: f
        def init_app(self, app):
            pass
        def __call__(self, *args, **kwargs):
            return self
    Limiter = _DummyLimiter
    def get_remote_address():  # pragma: no cover
        return "127.0.0.1"


from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_marshmallow import Marshmallow

# Initialise extensions
db = SQLAlchemy()
migrate = Migrate()
ma = Marshmallow()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
