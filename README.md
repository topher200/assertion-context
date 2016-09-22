Service to take Papertrail logs, parse out assertion information, and make cool charts.

TODO: describe each part here

We run everything in Docker, but there's some things you need to set up on the
host to get started. Installation instructions for setting up host:
 - yum install docker
 - pip install virtualenvwrapper
 - set up virtualenvwrapper
   - add this to your .bashrc:
```
export WORKON_HOME=$HOME/.virtualenvs
export PROJECT_HOME=$HOME/Devel
source /usr/local/bin/virtualenvwrapper.sh
```
    - source .bashrc
 - (if not installed) yum install -y python34-virtualenv
 - mkvirtualenv -p python3 <virtualenv name>
 - pip install -r requirements.txt
 - fill out web/.aws_credentials. requires these fields:
```
[default]
aws_access_key_id = ###
aws_secret_access_key = ###
```
  - (optional) fill out web/.aws_config as well. defaults to us-east-1

Then to start it all up:
  - ./server-start.sh

Once servers are started, tests can be run with
  - ./run-tests.sh
    - Note that this requires python3

---

elk/ is adapted from https://github.com/deviantony/docker-elk
