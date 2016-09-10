#!/bin/bash

nosetests --py3where web/app
pylint web/app/ --reports n
