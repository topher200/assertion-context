#!/bin/bash

docker build -t topher200/assertion-context . && \
    docker run \
           --env-file .env \
           --name assertion-context \
           --rm \
           $* \
           topher200/assertion-context
# docker logs -f assertion-context
