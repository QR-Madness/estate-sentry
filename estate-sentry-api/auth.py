from flask import Blueprint, request, jsonify
from flask import session as user_session
from werkzeug.security import generate_password_hash, check_password_hash

from db import SessionLocal
from db.models.user import User

auth_blueprint = Blueprint("EstateSentry:API:Auth", __name__)


def get_db_session():
    """
    Helper function to get a new database session.
    Initializes the database connection lazily, using the app's config.
    """
    return SessionLocal()


def get_user_from_session():
    """
    Retrieves a user from database using session tokens.
    :return: User object or None
    """
    user_session.get("user_token")
    user = get_db_session().query(User).filter(User.id == user_session.get("user_id"))
    return user


@auth_blueprint.route("/authenticate", methods=["POST"])
def authenticate():
    """
    Authenticate user via submitted login credentials.
    """
    # Extract JSON payload
    data = request.json
    username = data.get("username")
    pin = data.get("pin")
    password = data.get("password")

    if not username:
        return jsonify({"message": "Missing username"}), 400

    db_session = get_db_session()

    def respond_invalid_credentials():
        return jsonify({"message": "Invalid credentials"}), 401

    def respond_valid_credentials():
        user_token = user.generate_token()
        user_session["user_token"] = user_token
        return jsonify({"message": "Authentication successful"}), 200

    try:
        # get user by username
        user = db_session.query(User).filter(User.username == username).first()

        # ensure user exists
        if user is None:
            return respond_invalid_credentials()

        # verify credentials based on user's authentication method
        if user.auth_method == "username" and username == user.username:
            # username auth passed
            return respond_valid_credentials()
        elif user.auth_method == "pin" and user.pin == int(pin):
            # PIN auth passed
            return respond_valid_credentials()
        elif user.auth_method == "password" and check_password_hash(user.password, password):
            # password auth passed
            return respond_valid_credentials()

        return respond_invalid_credentials()
    except Exception as e:
        print(e)
        return respond_invalid_credentials()
    finally:
        db_session.close()


@auth_blueprint.route("/logout", methods=["POST"])
def logout():
    """
    Destroy user session (stub for logging out)
    """
    # In a complete application, manage session tokens properly
    try:
        user_token = user_session.pop("user_token", None)
        if user_token:
            return jsonify({"message": "Logout successful"}), 200
        else:
            return jsonify({"message": "Not logged in"}), 400
    except Exception as e:
        print(e)
        return jsonify({"message": "An error occurred"}), 500


@auth_blueprint.route("/register", methods=["POST"])
def register():
    """
    Register a new user.
    """
    # Extract JSON payload
    data = request.json
    username = data.get("username")
    auth_method = data.get("auth_method")
    pin = data.get("pin")
    password = data.get("password")
    name = data.get("name")
    # TODO: implement login_post_registration param

    # validate registration
    if not username:
        return jsonify({"message": "Missing username"}), 400
    elif auth_method not in ["username", "pin", "password"]:
        return jsonify({"message": "Invalid auth method, use PIN-based, password-based, or username-based."}), 400
    elif auth_method == "pin" and pin is None:
        return jsonify({"message": "Missing PIN"}), 400
    elif auth_method == "password" and password is None:
        return jsonify({"message": "Missing password"}), 400
    db_session = get_db_session()
    try:
        print("Adding new user: ", username, " ...")
        # Check if the username is already registered
        existing_user = db_session.query(User).filter(User.username == username).first()
        if existing_user:
            return jsonify({"message": "username is already registered"}), 409
        # hash the password (if any)
        hashed_password = None
        if password is not None:
            hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        # create and save the model
        new_user = User(username=username,  # metadata
                        name=name,  # define auth settings
                        auth_method=auth_method, password=hashed_password, pin=pin)
        db_session.add(new_user)
        db_session.commit()
        print("New user added")
        return jsonify({"message": "User registered successfully", "user_id": new_user.id}), 201
    except Exception as e:
        print(e)
    finally:
        db_session.close()


@auth_blueprint.route("/user-data", methods=["GET", "POST"])
def user_data():
    data = request.json
    username = data.get("username")
    db_session = get_db_session()
    # TODO only proceed if session is an admin or the requesting user
    try:
        user = db_session.query(User).filter(User.username == username).first()
        if request.method == "GET":
            # return user data
            return jsonify({"message": "User registered successfully", "user_id": user.id}), 201
        else:
            # TODO parse changes to user
            # TODO commit changes to user
            return jsonify({"message": "User data updated successfully"}), 200
    except Exception as e:
        print(e)
    finally:
        db_session.close()
