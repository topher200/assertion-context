#!/bin/bash

# import environment variables pointing to Badcorp services
set -a
source .badcorp.env
set +a

# add src to PYTHONPATH

# run the tests
PYTHONPATH=src pytest tests/test_bad_corp_to_papertrail.py
