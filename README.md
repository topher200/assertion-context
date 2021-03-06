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
We run everything in kubernetes. Please set up kubectl locally and connect to a 
kubernetes cluster. Then, on your development machine...
 - install kubernetes-helm
 - clone this repo
 - fill out .env with config variables. requires these fields:
```
DEBUG_LOGGING = False  # enables logging to file, very verbose

# token for Papertrail CLI access. used by realtime-updater
PAPERTRAIL_API_TOKEN=123456789012345678901234567890ab

# token for FullStory access. used to create links to FullStory
FULLSTORY_AUTH_TOKEN=123456789012345678901234567890ab

# databases/storage
ES_ADDRESS = <url to ElasticSearch database>
REDIS_ADDRESS = <url to Redis database>
USE_DOGPILE_CACHE = <True if we should use the dogpile cache>

# jira account to use for getting and creating issues
JIRA_SERVER = <url of the jira server. example: 'https://example.atlassian.net>
JIRA_BASIC_AUTH_USERNAME=name@server.com
JIRA_BASIC_AUTH_PASSWORD=hunter2
JIRA_PROJECT_KEY = <the project key of your JIRA project. example: 'SAN'>

# to download papertrail archives from s3
S3_BUCKET = <s3 bucket name. example: 'papertrail_log_bucket'>
S3_KEY_PREFIX = <prefix of papertrail logs in s3. example: 'papertrail/logs'>
AWS_ACCESS_KEY_ID=ASDFKJ87979898798798
AWS_SECRET_ACCESS_KEY=DFnkjdfkjdkFJDKFJkdsjfDFJKJKDFjkdfjkddkk # to download papertrail archives from s3
AWS_REGION=us-east-1 # to download papertrail archives from s3

# configuring the nginx AWS load balancer
AWS_SSL_CERT=arn:aws:acm:us-east-1:00000000000000:certificate/00000000-0000-0000-0000-000000000000
AWS_EXTRA_SECURITY_GROUP=sg-00000000000000
```
 - fill out .env.papertrail with config variables. requires these fields:
```
# logging
papertrail-destination=syslog://logs9.papertrailapp.com:12345
```

Then to start it all up:
 - `make fresh-deploy-to-k8s`

## Elasticsearch

For production, Elasticsearch database must be externally hosted. The IP of the
host server must be whitelisted.

Set up the mapping for the indexes by running `./scripts/setup-es-database.sh`

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
  
### Setting up dockerhub
Use this command to use a username and password to log into docker. This allows 
you to push built images to  dockerhub:
- `docker login`

## S3 and Lambda
### Papertrail
Enable Papertrail's "archive to s3" feature
  - http://help.papertrailapp.com/kb/how-it-works/automatic-s3-archive-export/

### Lambda
## s3 Log File -> Application
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

API_HOST_URL = # the URL of your app server
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

## Jira ticket update -> Application
Configure a webhook in Jira to send a message every time a Jira ticket is
updated. Point that webhook at an API gateway. Point the API gateway at a lambda
function like this:
```
import json

import requests

import config


print('Loading function')

API_HOST_URL = config.API_HOST_URL
API_ENDPOINT = config.API_ENDPOINT
API_REQUEST_URL = API_HOST_URL + API_ENDPOINT


def lambda_handler(event, _):
    print("Received event: " + json.dumps(event))

    key = json.loads(event['body'])['issue']['key']
    payload = {
        'issue_key': key
    }
    print('making request: %s' % payload)
    res = requests.put(API_REQUEST_URL, json=payload)
    if res.status_code == 200:
        print('Successfully updated "%s"' % key)
    elif res.status_code == 202:
        print('Successfully queued "%s"' % key)
    else:
        print(
            'request failed. received response: %s. our payload: "%s"' %
            (res.status_code, payload)
        )
        raise
    
    return {'key': key}
```

Where config.py is
```
API_HOST_URL = # the URL of your app server
API_ENDPOINT = '/api/update_jira_db'
```

## Istio
The istio template was created with this command:
```
helm template istio-1.0.2/install/kubernetes/helm/istio --name istio --namespace istio-system --set tracing.enabled=true --set global.proxy.includeIPRanges="109.96.0.1/16" -x templates/sidecar-injector-configmap.yaml > kubernetes-istio/istio.yaml
```
