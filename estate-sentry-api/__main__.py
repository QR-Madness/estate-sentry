from waitress import serve
from flask_app import create_app

if __name__ == '__main__':
    api = create_app(debug=True)
    if api.debug:
        api.run(host="0.0.0.0", port=13739)
    else:
        serve(api, host='0.0.0.0', port=13739)
