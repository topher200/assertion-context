#!/bin/bash

# import environment variables for server.py
set -a
source .env
set +a

# import environment variables pointing to Badcorp services
set -a
source .badcorp.env
set +a

# run the tests
nosetests --py3where src --quiet
