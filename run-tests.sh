#!/bin/bash

nosetests web/app
pylint web/app/ --reports n
