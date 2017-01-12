"""
    Run our API.

    Provides endpoints for saving data to DB and for analyzing the data that's been saved.
"""
import collections
import datetime
import logging
import os

import flask
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

# location to save posts
POST_SAVE_DIR = '/srv/posts'

# jekyll post template
POST_TEMPLATE = '''---
layout: post
title: Traceback
---
{{% highlight python %}}
{}
{{% endhighlight %}}'''


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

    # use our powerful parser to check out the requested file
    log_line_generator = s3.parse_s3_file(json_request['bucket'], json_request['key'])
    if log_line_generator is None:
        return 'error accessing s3', 502

    # save the parser output to the database
    for line in log_line_generator:
        flask_app.logger.debug('saving log line: %s', line)
        database.save_log_line(ES, line)

    return 'success'


@flask_app.route("/api/loglines", methods=['GET'])
def get_loglines():
    _ = database.get_loglines(ES)
    return 'success'


@flask_app.route("/api/generate_posts", methods=['PUT'])
def generate_posts():
    # get all loglines
    loglines = database.get_loglines(ES)

    # group loglines by origin id
    loglines_by_origin_id = collections.defaultdict(list)
    for logline in loglines:
        loglines_by_origin_id[logline.origin_papertrail_id].append(logline)

    # for each set of loglines by origin id, create a traceback
    for _, loglines in loglines_by_origin_id.items():
        # sort the loglines in reverse order, so the bottom of the traceback is last
        sorted_loglines = sorted(loglines, key=lambda x: x.line_number, reverse=True)

        # combine the loglines into a cohesive traceback
        traceback = ''.join((l.parsed_log_message for l in sorted_loglines))

        # create a post with the traceback
        post = POST_TEMPLATE.format(traceback)

        # create a title using the origin id/timestamp
        timestamp = sorted_loglines[-1].timestamp
        papertrail_id = sorted_loglines[-1].origin_papertrail_id
        filename = '%s-%s.md' % (timestamp.strftime('%Y-%m-%d-%H_%M_%S'), papertrail_id)
        flask_app.logger.debug('creating post "%s" with %s loglines', filename, len(loglines))

        # save post to disk
        with open(os.path.join(POST_SAVE_DIR, filename), 'w') as f:
            f.write(post)

    return 'success'

@flask_app.before_first_request
def setup_logging():
    if not flask_app.debug:
        # In production mode, add log handler to sys.stderr.
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            "%H:%M:%S"
        )
        handler.setFormatter(formatter)
        flask_app.logger.addHandler(handler)
        flask_app.logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    http_server = WSGIServer(('', 5000), DebuggedApplication(flask_app))
    http_server.serve_forever()
