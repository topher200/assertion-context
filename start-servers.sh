#!/bin/bash

# first, we manually make sure that the web app containers are stopped. this is
# required since we dynamically update their files using a volume; unlike other
# containers, docker won't notice all the changes we make to their files
docker-compose stop web celery

# build and start all services
docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml up -d --build "$@"
