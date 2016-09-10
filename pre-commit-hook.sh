#!/bin/bash

git stash -q --keep-index

python web/app/test.py || exit 1

git stash pop -q
