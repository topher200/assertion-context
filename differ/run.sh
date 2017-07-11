#!/bin/bash

diff <(sed -e 's/^.*debug:  //' diff1.txt) <(sed -e 's/^.*debug:  //' diff2.txt)
# diff <(sed -e 's/^.*debug:  //' diff1.txt | grep token) <(sed -e 's/^.*debug:  //' diff2.txt | grep token)

