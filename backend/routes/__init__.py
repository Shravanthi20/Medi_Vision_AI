from flask import Flask

from .bills import bills_bp
from .core import core_bp
from .inventory import inventory_bp
from .masters import masters_bp
from .sms import sms_bp
from .purchases import purchases_bp
from .communications import communications_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(core_bp)
    app.register_blueprint(bills_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(purchases_bp)
    app.register_blueprint(masters_bp)
    app.register_blueprint(communications_bp)
    app.register_blueprint(sms_bp)
