#!/bin/bash

# import environment variables for server.py
set -a
source .env
set +a

# import environment variables pointing to Badcorp services
set -a
source .badcorp.env
set +a

cd src
if [ "$1" == "--skip-integration-tests" ]
then
    python -m pytest --ignore-glob *_integration_test*
else
    python -m pytest
fi
