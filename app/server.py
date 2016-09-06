import flask

import main


app = flask.Flask(__name__)


@app.route("/api/parse_s3", methods=['POST'])
def parse_s3():
    json_request = flask.request.get_json()
    app.logger.debug('req: %s', json_request)
    if not all(json_request.has_key(k) for k in ('bucket', 'key')):
        return 'missing params', 400
    main.parse_s3_file(json_request['bucket'], json_request['key'])
    return 'success'


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
