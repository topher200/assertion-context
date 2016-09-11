"""
    Run our API
"""
import flask
from flask_elasticsearch import FlaskElasticsearch

from app import s3
from app.logline import LogLine


# start app
flask_app = flask.Flask(__name__)

# configuration
flask_app.config['DEBUG'] = True
flask_app.config['ELASTICSEARCH_HOST'] = "elasticsearch:9200"

# set up database
es = FlaskElasticsearch(flask_app)


def save_log_line(log_line):
    """
    Takes a L{LogLine} and saves it to the database
    """
    assert isinstance(log_line, LogLine), (type(log_line), log_line)
    doc = log_line.document()
    es.index(
        index='logline-index',
        doc_type='logline',
        body=doc
    )


@flask_app.route("/api/parse_s3", methods=['POST'])
def parse_s3():
    # parse our input
    json_request = flask.request.get_json()
    flask_app.logger.debug('req: %s', json_request)
    if not all(k in json_request for k in ('bucket', 'key')):
        return 'missing params', 400

    # use our powerful parser to check out the requested file
    log_line_generator = s3.parse_s3_file(json_request['bucket'], json_request['key'])
    if log_line_generator is None:
        return 'error accessing s3', 502

    # save the parser output to the database
    for line in log_line_generator:
        save_log_line(line)

    return 'success'


if __name__ == "__main__":
    flask_app.run(host='0.0.0.0')
