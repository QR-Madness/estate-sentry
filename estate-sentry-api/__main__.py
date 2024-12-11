from flask import Flask, request, jsonify
from waitress import serve
from auth import auth_blueprint

api = Flask(__name__)
api.register_blueprint(auth_blueprint)
api.debug = True

if __name__ == '__main__':
    if api.debug:
        api.run(host="0.0.0.0", port=13739)
    else:
        serve(api, host='0.0.0.0', port=13739)