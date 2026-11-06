"""
Flask application entrypoint for deploy-utils/fs.
Run locally: flask --app app run --port 8004
"""

import os

from flask import Flask

from engine import init_auth_db
from routes import bp


def create_app(init_db: bool = True) -> Flask:
    app = Flask(__name__)
    if init_db:
        init_auth_db()
    app.register_blueprint(bp)
    return app


def _default_app() -> Flask:
    init_on_import = os.environ.get("FS_SKIP_INIT_DB") != "1"
    return create_app(init_db=init_on_import)


app = _default_app()
