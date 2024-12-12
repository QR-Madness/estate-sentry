from flask import Flask
from waitress import serve

from auth import auth_blueprint

api = Flask(__name__)
api.register_blueprint(auth_blueprint)

if __name__ == '__main__':
    api.debug = True  # TEMPORARY
    if api.debug:
        api.run(host="0.0.0.0", port=13739)
    else:
        serve(api, host='0.0.0.0', port=13739)
