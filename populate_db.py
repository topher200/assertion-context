#!/usr/bin/env python3

import requests


API_REQUEST_URL = 'http://127.0.0.1:80/api/parse_s3'
S3_BUCKET = "papertrail.wordstream.com"
S3_KEY_PREFIX = 'papertrail/logs'
DATES_TO_PROCESS = (
    '2016-09-10',
)

def build_keys():
    """
        Yields a generator of un-prefixed keys to process

        Uses DATES_TO_PROCESS, and gets a key for each of the 24 hours in that day.
    """
    for date_ in DATES_TO_PROCESS:
        for time_ in range(0, 24):
            yield '%s/dt=%s-%s.tsv.gz' % (date_, date_, time_)


def main():
    for key in build_keys():
        payload = {
            "bucket": S3_BUCKET,
            "key": '/'.join((S3_KEY_PREFIX, key)),
        }
        res = requests.post(API_REQUEST_URL, json=payload)
        print('tried "%s", received %s' % (key, res.status_code))

        import time
        time.sleep(1)


if __name__ == "__main__":
    main()
