from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from db.models.user import User
from db.session import SessionLocal

auth_blueprint = Blueprint('EstateSentry:API:Auth', __name__)


@auth_blueprint.route('/authenticate', methods=['POST'])
def authenticate():
    """
    Authenticate user via submitted login credentials.
    """
    # Extract JSON payload
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Missing email or password"}), 400

    session = SessionLocal()
    try:
        # Query user by email
        user = session.query(User).filter(User.email == email).first()
        if user and check_password_hash(user.password, password):
            return jsonify({"message": "Authentication successful", "user_id": user.id}), 200
        else:
            return jsonify({"message": "Invalid email or password"}), 401
    finally:
        session.close()


@auth_blueprint.route('/logout', methods=['POST'])
def logout():
    """
    Destroy user session (stub for logging out)
    """
    # In a complete application, manage session tokens properly
    return jsonify({"message": "User logged out"}), 200


@auth_blueprint.route('/register', methods=['POST'])
def register():
    """
    Register a new user.
    """
    # Extract JSON payload
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"message": "Missing name, email, or password"}), 400

    session = SessionLocal()
    try:
        # Check if the email is already registered
        existing_user = session.query(User).filter(User.email == email).first()
        if existing_user:
            return jsonify({"message": "Email is already registered"}), 409

        # Generate hashed password
        hashed_password = generate_password_hash(password, method='sha256')

        # Create a new user
        new_user = User(name=name, email=email, password=hashed_password)
        session.add(new_user)
        session.commit()

        return jsonify({"message": "User registered successfully", "user_id": new_user.id}), 201
    finally:
        session.close()
