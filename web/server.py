"""
    Run our API.

    Provides endpoints for saving data to DB and for analyzing the data that's been saved.
"""
import flask
from flask_elasticsearch import FlaskElasticsearch
from gevent.wsgi import WSGIServer

from app import database
from app import s3


# start app
flask_app = flask.Flask(__name__)

# configuration
flask_app.config['DEBUG'] = False
flask_app.config['ELASTICSEARCH_HOST'] = "elasticsearch:9200"

# set up database
es = FlaskElasticsearch(flask_app)


@flask_app.route("/api/parse_s3", methods=['POST'])
def parse_s3():
    """
        POST request to parse the data from a Papertrail log hosted on s3.

        Takes a JSON containing these fields:
        - bucket: the name of the s3 bucket containing the file. string
        - key: the filename of the file we should parse. must be in `bucket`. string

        All fields are required.

        Returns a 400 error on bad input. Returns a 502 if we get an error accessing s3. Returns a
        200 on success.
    """
    # parse our input
    json_request = flask.request.get_json()
    flask_app.logger.debug('req: %s', json_request)
    if json_request is None or not all(k in json_request for k in ('bucket', 'key')):
        return 'missing params', 400

    # use our powerful parser to check out the requested file
    log_line_generator = s3.parse_s3_file(json_request['bucket'], json_request['key'])
    if log_line_generator is None:
        return 'error accessing s3', 502

    # save the parser output to the database
    for line in log_line_generator:
        database.save_log_line(es, line)

    return 'success'


@flask_app.route("/api/generate_chart", methods=['GET'])
def generate_chart():
    pass


if __name__ == "__main__":
    http_server = WSGIServer(('', 5000), flask_app)
    http_server.serve_forever()
