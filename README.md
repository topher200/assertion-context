Parses Papertrail logs to show context and historical reflection of Python assertions.

At a high level, here's the steps we perform:
- Papertrail generates archives of all its logs once per hour
- S3 triggers a Lambda function that calls our API (passing along the new log file's filename)
- we download the log file and parse it for Python tracebacks. we save the tracebacks to ElasticSearch
- we provide a Jinja templated site to show these tracebacks to our users

[![Build Status](https://travis-ci.org/topher200/assertion-context.svg?branch=master)](https://travis-ci.org/topher200/assertion-context)

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
 - `pip install docker-compose`
   - optional: do this in a virtualenv
 - clone this repo
 - fill out `web/.aws_credentials` for a user that has S3 read permissions to
   the papertrail archives. this is used for our app to download the archives
   from S3. requires these fields:
```
[default]
aws_access_key_id = ###
aws_secret_access_key = ###
```
 - (optional) fill out `web/.aws_config` as well. defaults to us-east-1
 - fill out `web/instance/config.py`. requires these fields:
```
OAUTH_CLIENT_ID = <from your oauth provider>
OAUTH_CLIENT_SECRET = <from your oauth provider>
ES_ADDRESS = <url to ElasticSearch database>
REDIS_ADDRESS = <url to Redis database>
USE_DOGPILE_CACHE = <True if we should use the dogpile cache>
AUTHORIZED_EMAIL_REGEX = <regex checked against the google oauth'd email of the user. example: '@gmail.com$'>
JIRA_SERVER = <url of the jira server. example: 'https://example.atlassian.net>
JIRA_BASIC_AUTH = (<jira username>, <jira password>)
JIRA_PROJECT_KEY = <the project key of your JIRA project. example: 'SAN'>
DEBUG = False  # enables debug logging to file
S3_BUCKET = <s3 bucket name. example: 'papertrail_log_bucket'>
S3_KEY_PREFIX = <prefix of papertrail logs in s3. example: 'papertrail/logs'>
```
 - fill out .env for docker-compose variables. requires these fields:
```
PAPERTRAIL_PRODUCTION_URL=udp://logs4.papertrailapp.com:35000
PAPERTRAIL_DEVELOPMENT_URL=udp://logs4.papertrailapp.com:31000
```
 - fill out web/realtime_updater/.papertrail.yml for real-time papertrail. requires this field:
```
token: 123456789012345678901234567890ab
```


Then to start it all up:
 - `make run-local` or `make run-prod`
  - start-servers runs its own elasticsearch, where production-servers uses an externally hosted one

## Elasticsearch

For production, Elasticsearch database must be externally hosted. The IP of the
host server must be whitelisted.

This index should be set up with this mapping:
```
PUT traceback-index
{
  "settings": {
    "analysis": {
      "analyzer": {
        "traceback_filtered": {
          "type": "custom",
          "tokenizer": "letter",
          "char_filter": [
            "newrelic_and_underscore_filter"
          ]
        }
      },
      "char_filter": {
        "newrelic_and_underscore_filter": {
          "type": "pattern_replace",
          "pattern": "_|args|File|framework_cherrypy.py|handler_wrapper|hooks|in|kwargs|lib|line|local|newrelic|opt|packages|python2.7|return|site|venv|wordstream_virtualenv|wrapped",
          "replacement": ""
        }
      }
    }
  },
  "mappings": {
    "traceback": {
      "properties": {
        "traceback_text": {
          "analyzer": "traceback_filtered",
          "type": "text"
        }
      }
    }
  }
}
PUT jira-issue-index
{
  "settings": {
    "analysis": {
      "analyzer": {
        "traceback_filtered": {
          "type": "custom",
          "tokenizer": "letter",
          "char_filter": [
            "newrelic_and_underscore_filter"
          ]
        }
      },
      "char_filter": {
        "newrelic_and_underscore_filter": {
          "type": "pattern_replace",
          "pattern": "_|args|File|framework_cherrypy.py|handler_wrapper|hooks|in|kwargs|lib|line|local|newrelic|opt|packages|python2.7|return|site|venv|wordstream_virtualenv|wrapped",
          "replacement": ""
        }
      }
    }
  },
  "mappings": {
    "jira-issue": {
      "properties": {
        "description": {
          "analyzer": "traceback_filtered",
          "type": "text"
        },
        "comments": {
          "analyzer": "traceback_filtered",
          "type": "text"
        },
        "description_filtered": {
          "analyzer": "traceback_filtered",
          "type": "text"
        },
        "comments_filtered": {
          "analyzer": "traceback_filtered",
          "type": "text"
        }
      }
    }
  }
}
```

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
   - (if not installed) `yum install -y python34-virtualenv`
 - mkvirtualenv -p python3 <virtualenv name>
 - pip install -r requirements.txt

### Running
Once python is installed, tests can be run with
  - `make test`

## S3 and Lambda
### Papertrail
Enable Papertrail's "archive to s3" feature
  - http://help.papertrailapp.com/kb/how-it-works/automatic-s3-archive-export/

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
    if res.status_code in (200, 202):
        print('Successfully parsed "%s"' % key)
    else:
        print('Parse request received %s. data: "%s"' % (res.status_code, payload))
        raise Exception('parse request failed. payload: %s', payload)
```
