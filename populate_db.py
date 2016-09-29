#!/usr/bin/env python3

import time
import requests


API_REQUEST_URL = 'http://127.0.0.1:80/api/parse_s3'
S3_BUCKET = "papertrail.wordstream.com"
S3_KEY_PREFIX = 'papertrail/logs'
MONTHS_TO_PROCESS = (
    '2016-09-%02d',
)

def build_keys():
    """
        Yields a generator of un-prefixed keys to process

        Uses DATES_TO_PROCESS, and gets a key for each of the 24 hours in that day.
    """
    for month in MONTHS_TO_PROCESS:
        for day in range(1, 32):
            date_ = month % day
            for time_ in range(0, 24):
                yield 'dt=%s/%s-%02d.tsv.gz' % (date_, date_, time_)


def main():
    for key in build_keys():
        payload = {
            "bucket": S3_BUCKET,
            "key": '/'.join((S3_KEY_PREFIX, key)),
        }
        print('Making request to "%s" with "%s"' % (API_REQUEST_URL, payload))
        res = requests.post(API_REQUEST_URL, json=payload)
        if res.status_code == 200:
            print('Successfully parsed "%s"' % key)
        else:
            print('Parse request received %s. data: "%s"' % (res.status_code, payload))
            time.sleep(1)  # rate limiting ourselves


if __name__ == "__main__":
    main()
