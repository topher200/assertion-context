#!/bin/bash

# import environment variables for server.py
set -a
source .env
set +a

# import environment variables pointing to Badcorp services
set -a
source .badcorp.env
set +a

# add src to PYTHONPATH and run the tests
PYTHONPATH=src pytest tests/test_run_integration_tests.py
