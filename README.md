Parses Papertrail logs to show context and historical reflection of Python assertions.

At a high level, here's the steps we perform:
- Papertrail generates archives of all its logs once per hour
- S3 triggers a Lambda function that calls our API (passing along the new log file's filename)
- we download the log file and parse it for Python tracebacks. we save the tracebacks to ElasticSearch
- we provide a Jinja templated site to show these tracebacks to our users

= Parsing Papertrail logs

We take the archived Papertrail logs in .tsv.gz format and unzip them. We search
them for any errors. When an error is found, we go backwards in the logs to find
the root cause (context) of the assertion, which includes the traceback and the
log lines before the traceback. We do this by determining the instance ID of the
machine that had the assertion and searching the logs for the lines on that
machine previous to the offending line.

= Getting it set up
== Server installation instructions
We run everything in Docker, but there's some things you need to set up on the
host to get started. Installation instructions for setting up the host:
 - install docker
  - http://docs.aws.amazon.com/AmazonECS/latest/developerguide/docker-basics.html
 - fill out web/.aws_credentials. requires these fields:
```
[default]
aws_access_key_id = ###
aws_secret_access_key = ###
```
  - (optional) fill out web/.aws_config as well. defaults to us-east-1
  - fill out web/.es_credentials. the file should be a single line containing only the Elasticsearch URL

Then to start it all up:
  - ./start-servers.sh

Elasticsearch database must be externally hosted. The IP of this server must be whitelisted.

== Running tests
=== Setup - install Python locally
 - pip install virtualenvwrapper
 - set up virtualenvwrapper
   - add this to your .bashrc:
```
export WORKON_HOME=$HOME/.virtualenvs
export PROJECT_HOME=$HOME/Devel
source /usr/local/bin/virtualenvwrapper.sh
```
 - `source .bashrc` to enable virtualenvwrapper
 - (if not installed) yum install -y python34-virtualenv
 - mkvirtualenv -p python3 <virtualenv name>
 - pip install -r requirements.txt

=== Running
Once servers are started and python is installed, tests can be run with
  - ./run-tests.sh

== S3 and Lambda
=== Papertrail
Enable Papertrail's "archive to s3" feature

=== Lambda
Create an SNS topic to trigger a Lambda function whenever a Papertrail log file
is added to your s3 archive. The Lambda function should call our api
(/api/parse_s3) with the bucket and key of the log file.

TODO: example here:

== References
elk/ is adapted from https://github.com/deviantony/docker-elk
