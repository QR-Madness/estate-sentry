from flask import Flask

from auth import auth_blueprint
from db import DEFAULT_TESTING_DATABASE_URL, DEFAULT_DATABASE_URL


def create_app(debug=False, test_mode=False):
    """
    API app factory.
    :param debug: Enable debug mode.
    :param test_mode: Connect to testing services (and DB).
    :return: Configured Flask app.
    """
    app = Flask(__name__, instance_relative_config=test_mode)
    if test_mode:
        app.debug = True
        app.config["TEST_MODE"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = DEFAULT_TESTING_DATABASE_URL
    else:
        app.debug = debug
        app.config["SQLALCHEMY_DATABASE_URI"] = DEFAULT_DATABASE_URL
    app.register_blueprint(auth_blueprint)
    return app
