#!/bin/bash

nosetests --py3where web || exit 1
pylint --load-plugins pylint_flask web --reports n
