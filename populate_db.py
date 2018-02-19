#!/usr/bin/env python3

"""Populate our elasticsearch db with Papertrail data from S3"""

import argparse
import time
import requests


MONTHS_TO_PROCESS = (
    '2018-02-%02d',
)

def build_dates():
    """
        Yields a generator of dates to process

        Uses MONTHS_TO_PROCESS, and gets a date for each of the days in each month. We do our
        calculations naively; months with fewer with 31 days will get 31 days anyway.
    """
    for month in MONTHS_TO_PROCESS:
        for day in range(1, 32):
            date_ = month % day
            yield date_


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-request-url', help='the location of our API to hit',
                        default='http://127.0.0.1:8080/api/parse_s3_day')
    args = parser.parse_args()

    for date_ in build_dates():
        payload = {
            "date": date_
        }
        for _ in range(5):  # retry a few times on failure
            print('Making request to "%s" with "%s"' % (args.api_request_url, payload))
            res = requests.post(args.api_request_url, json=payload)
            if res.status_code == 202:
                print('Successfully queued "%s"' % date_)
                break  # success! we're done with this one
            else:
                print('Parse failed. status: %s. data: "%s"' % (res.status_code, payload))
                time.sleep(1)  # rate limiting ourselves


if __name__ == "__main__":
    main()
