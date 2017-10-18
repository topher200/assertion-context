#!/usr/bin/env python3

"""Populate our elasticsearch db with Papertrail data from S3"""

import argparse
import time
import requests


MONTHS_TO_PROCESS = (
    '2017-07-%02d',
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--s3-bucket',
                        help='s3 bucket to retrieve files from. example: "example.company.com"')
    parser.add_argument('--s3-key-prefix',
                        help='s3 key to retrieve files from. example: "path/to/logs"')
    parser.add_argument('--api-request-url', help='the location of our API to hit',
                        default='http://127.0.0.1:8080/api/parse_s3')
    args = parser.parse_args()

    for key in build_keys():
        payload = {
            "bucket": args.s3_bucket,
            "key": '/'.join((args.s3_key_prefix, key)),
        }
        for _ in range(5):  # retry a few times on failure
            print('Making request to "%s" with "%s"' % (args.api_request_url, payload))
            res = requests.post(args.api_request_url, json=payload)
            if res.status_code == 200:
                print('Successfully parsed "%s"' % key)
                break  # success! we're done with this one
            if res.status_code == 202:
                print('Successfully queued "%s"' % key)
                break  # success! we're done with this one
            else:
                print('Parse failed. status: %s. data: "%s"' % (res.status_code, payload))
                time.sleep(1)  # rate limiting ourselves


if __name__ == "__main__":
    main()
