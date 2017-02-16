"""
    Run our API.

    Provides endpoints for saving data to DB and for analyzing the data that's been saved.
"""
import logging
import os

import flask
from flask_bootstrap import Bootstrap
from flask_elasticsearch import FlaskElasticsearch
from gevent.wsgi import WSGIServer
from werkzeug.debug import DebuggedApplication

from app import database
from app import s3


# start app
flask_app = flask.Flask(__name__)

# configuration
flask_app.config['ELASTICSEARCH_HOST'] = "elasticsearch:9200"

# set up database
ES = FlaskElasticsearch(flask_app)

# add bootstrap
Bootstrap(flask_app)


@flask_app.route("/", methods=['GET'])
def index():
    flask_app.logger.debug('handling index request')
    return flask.render_template('index.html', tracebacks=database.get_tracebacks(ES))


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
    flask_app.logger.info('parse s3 request: %s', json_request)
    if json_request is None or not all(k in json_request for k in ('bucket', 'key')):
        return 'missing params', 400

    # use our powerful parser to run checks on the requested file
    traceback_generator = s3.parse_s3_file(json_request['bucket'], json_request['key'])
    if traceback_generator is None:
        return 'error accessing s3', 502

    # save the parser output to the database
    for traceback in traceback_generator:
        flask_app.logger.debug('saving traceback: %s', traceback)
        database.save_traceback(ES, traceback)

    return 'success'


@flask_app.route("/api/tracebacks", methods=['GET'])
def get_tracebacks():
    data = [tb.document() for tb in database.get_tracebacks(ES)]
    return flask.jsonify({'tracebacks': data})


@flask_app.before_first_request
def setup_logging():
    # add log handler to sys.stderr.
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        "%H:%M:%S"
    )
    handler.setFormatter(formatter)
    flask_app.logger.addHandler(handler)
    flask_app.logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    flask_app.run(debug=True, host='0.0.0.0', port=8000)
