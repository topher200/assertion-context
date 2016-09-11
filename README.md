Service to take Papertrail logs, parse out assertion information, and make cool charts.

TODO: describe each part here

We run everything in Docker, but there's some things you need to set up on the
host to get started. Installation instructions for setting up host:
 - mkvirtualenv python3 <virtualenv name>
 - pip install -r requirements.txt
 - Docker (docker-compose)

Then to start it all up:
 - ./server-start.sh

elk/ is adapted from https://github.com/deviantony/docker-elk
