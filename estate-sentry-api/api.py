from flask import Flask
from flask_session import Session

from auth import auth_blueprint
from db import DEFAULT_TESTING_DATABASE_URL, DEFAULT_DATABASE_URL

SESSION_TYPE = 'SQLAlchemy'


def create_app(debug=False, test_mode=False):
    """
    API app factory.
    :param debug: Enable debug mode.
    :param test_mode: Connect to testing services (and DB).
    :return: Configured Flask app.
    """
    app = Flask(__name__, instance_relative_config=test_mode)
    # Initialize Flask-Session with the app reference
    # https://pypi.org/project/Flask-Session/
    app.config.from_object(__name__)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if test_mode:
        app.debug = True
        app.config["TEST_MODE"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = DEFAULT_TESTING_DATABASE_URL
    else:
        app.debug = debug
        app.config["SQLALCHEMY_DATABASE_URI"] = DEFAULT_DATABASE_URL
    Session(app)
    app.register_blueprint(auth_blueprint)
    return app
