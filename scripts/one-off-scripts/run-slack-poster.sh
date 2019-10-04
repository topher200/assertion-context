#!/bin/bash

cd $(dirname $0)
cd ..
export $(grep -v '^#' .env | xargs) && python web/send_example_message_to_slack.py

