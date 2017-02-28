#!/bin/bash

# first, we manually make sure that the web app is stopped. this is required
# since we dynamically update its files using a volume; unlike other containers,
# docker won't notice all the changes we make to its files
docker-compose stop web

# build and start all services
docker-compose -f docker-compose.yaml up -d --build "$@"
