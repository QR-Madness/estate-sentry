"""
Authentication API: Manage/access user accounts on the Estate Sentry server.
"""
from flask import Blueprint, request

auth_blueprint = Blueprint('EstateSentry:API:Auth', __name__)


@auth_blueprint.route('/authenticate', methods=['GET', 'POST'])
def authenticate():
    """
    Authenticate user via submitted login credentials.
    """
    if request.method == 'GET':
        # TODO verify authenticity of user token
        pass
    else:
        # TODO process login attempt
        pass

@auth_blueprint.route('/logout', methods=['POST'])
def logout():
    """
    Destroy user session
    """
    pass

@auth_blueprint.route('/register', methods=['POST'])
def register():
    # TODO verify user is an admin
    # TODO create the user
    pass
