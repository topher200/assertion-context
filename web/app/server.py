"""
    Run our API
"""
import flask
from flask_elasticsearch import FlaskElasticsearch

from . import s3

# configuration
DEBUG = True
ELASTICSEARCH_HOST = "localhost:9200"

# start app
flask_app = flask.Flask(__name__)

# database
es = FlaskElasticsearch(flask_app)


@flask_app.route("/api/parse_s3", methods=['POST'])
def parse_s3():
    json_request = flask.request.get_json()
    flask_app.logger.debug('req: %s', json_request)
    if not all(k in json_request for k in ('bucket', 'key')):
        return 'missing params', 400
    s3.parse_s3_file(json_request['bucket'], json_request['key'])
    return 'success'


if __name__ == "__main__":
    flask_app.run(host='0.0.0.0', debug=True)
