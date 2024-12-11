from flask import Blueprint

auth_blueprint = Blueprint('EstateSentry:API:Auth', __name__)


@auth_blueprint.route('/authenticate', methods=['POST'])
def authenticate():
    pass
