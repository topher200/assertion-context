#!/bin/bash

diff <(sed -e 's/^.*debug:  //' diff1.txt) <(sed -e 's/^.*debug:  //' diff2.txt)

