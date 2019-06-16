#!/bin/bash

# import environment variables pointing to Badcorp services
set -a
source .badcorp.env
set +a

# run the tests
python -m unittest src/test/test_bad_corp_to_papertrail.py
