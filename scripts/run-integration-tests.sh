#!/bin/bash

# import environment variables pointing to Badcorp services
set -a
source .badcorp.env
set +a

# add src to PYTHONPATH

# run the tests
PYTHONPATH=src pytest tests/test_run_integration_tests.py
