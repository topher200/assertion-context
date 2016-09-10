#!/bin/bash

nosetests --py3where web/app
pylint --load-plugins pylint_flask web/app/ --reports n
