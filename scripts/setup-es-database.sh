#!/bin/bash

# Set up our indexes with their required mappings.
#
# NOTE: we don't check to confirm that the indexes don't already exist. this
# script may throw errors; if they indexes have already been mapped it's safe to
# ignore those errors.

# import environment variables
set -a
source .env
set +a

curl -X PUT \
     "$ES_ADDRESS:9200/traceback-index" \
     -H 'Content-Type: application/json' \
     -d @scripts/es_mappings/traceback_index.json

echo "\n"

curl -X PUT \
     "$ES_ADDRESS:9200/jira-issue-index" \
     -H 'Content-Type: application/json' \
     -d @scripts/es_mappings/jira_issue_index.json
