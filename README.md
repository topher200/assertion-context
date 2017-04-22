Parses Papertrail logs to show context and historical reflection of Python assertions.

At a high level, here's the steps we perform:
- Papertrail generates archives of all its logs once per hour
- S3 triggers a Lambda function that calls our API (passing along the new log file's filename)
- we download the log file and parse it for Python tracebacks. we save the tracebacks to ElasticSearch
- we provide a Jinja templated site to show these tracebacks to our users

# Parsing Papertrail logs

We take the archived Papertrail logs in .tsv.gz format and unzip them. We search
them for any errors. When an error is found, we go backwards in the logs to find
the root cause (context) of the assertion, which includes the traceback and the
log lines before the traceback. We do this by determining the instance ID of the
machine that had the assertion and searching the logs for the lines on that
machine previous to the offending line.

# Getting it set up
## Server installation instructions
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
 - fill out instance/config.py. requires these fields:
```
OAUTH_CLIENT_ID = <from your oauth provider>
OAUTH_CLIENT_SECRET = <from your oauth provider>
ES_ADDRESS = <url to ElasticSearch database>
AUTHORIZED_EMAIL_REGEX = <regex checked against the google oauth'd email of the user. example: '@gmail.com$'>
JIRA_SERVER = <url of the jira server. example: 'https://example.atlassian.net>
JIRA_BASIC_AUTH = (<jira username>, <jira password>)
JIRA_PROJECT_KEY = <the project key of your JIRA project. example: 'SAN'>
```
 - fill out .env for docker-compose variables. requires these fields:
```
PAPERTRAIL_PRODUCTION_URL=udp://logs4.papertrailapp.com:35000
PAPERTRAIL_DEVELOPMENT_URL=udp://logs4.papertrailapp.com:31000
```

Then to start it all up:
 - ./start-servers.sh

Elasticsearch database must be externally hosted. The IP of this server must be whitelisted.

## Running tests
### Setup - install Python locally
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

### Running
Once servers are started and python is installed, tests can be run with
  - ./run-tests.sh

## S3 and Lambda
### Papertrail
Enable Papertrail's "archive to s3" feature

### Lambda
Create an SNS topic to trigger a Lambda function whenever a Papertrail log file
is added to your s3 archive. The Lambda function should call our api
(/api/parse_s3) with the bucket and key of the log file.

Example lambda function:

```
import json
import requests
import urllib
import boto3

print('Loading function')

s3 = boto3.client('s3')

API_HOST_URL = 'http://ec2-8-8-8-8.compute-1.amazonaws.com'
API_ENDPOINT = '/api/parse_s3'
API_REQUEST_URL = API_HOST_URL + API_ENDPOINT


def lambda_handler(event, context):
    # print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))
    payload = {
        "bucket": bucket,
        "key": key,
    }
    print payload
    res = requests.post(API_REQUEST_URL, json=payload)
    if res.status_code == 200:
        print('Successfully parsed "%s"' % key)
    else:
        print('Parse request received %s. data: "%s"' % (res.status_code, payload))
```
