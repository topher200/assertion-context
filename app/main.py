"""
Parse a given file. Takes a filename or s3 bucket/key combo.

One of --filename or a --s3-bucket/--s3-key pair is required.
"""


import argparse
import datetime
import tempfile
import time

import boto3

import file_parser


def main():
    start_time = time.time()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--filename', help='filename to parse')
    parser.add_argument('--s3-bucket', help='bucket of file to parse')
    parser.add_argument('--s3-key', help='key of file to parse')
    args = parser.parse_args()
    filename = args.filename
    s3_bucket = args.s3_bucket
    s3_key = args.s3_key

    assert (s3_bucket is None) == (s3_key is None), (s3_bucket, s3_key)  # must have both or neither
    assert (s3_bucket is None) != (filename is None), (
        s3_bucket, filename)  # must have one but not both

    if filename:
        print "running with %s" % filename
        file_parser.parse_gzipped_file(filename)
    else:
        print "running from s3: %s:%s" % (s3_bucket, s3_key)
        s3 = boto3.client('s3')
        with tempfile.NamedTemporaryFile('wb', delete=False) as local_file:
            s3.download_fileobj(s3_bucket, s3_key, local_file)

        print "running with %s" % local_file.name
        print file_parser.parse_gzipped_file(local_file.name)

    print 'program executed in %s' % datetime.timedelta(seconds=time.time() - start_time)


if __name__ == "__main__":
    main()
