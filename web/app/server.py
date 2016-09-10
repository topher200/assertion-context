"""
    Run our API
"""
import flask
from flask_elasticsearch import FlaskElasticsearch

from app import s3


# start app
flask_app = flask.Flask(__name__)
flask_app.config.from_object('config')

# database
es = FlaskElasticsearch(flask_app)


def save_log_line(log_line):
    """
    Takes a L{LogLine} and saves it to the database
    """
    assert isinstance(log_line, LogLine), (type(log_line), log_line)
    print es.ping()


@flask_app.route("/api/parse_s3", methods=['POST'])
def parse_s3():
    json_request = flask.request.get_json()
    flask_app.logger.debug('req: %s', json_request)
    if not all(json_request.has_key(k) for k in ('bucket', 'key')):
        return 'missing params', 400
    s3.parse_s3_file(json_request['bucket'], json_request['key'])
    return 'success'


if __name__ == "__main__":
    flask_app.run(host='0.0.0.0', debug=True)
