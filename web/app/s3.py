"""
    Parse a file living on s3
"""
import tempfile

import boto3

from . import file_parser


def parse_s3_file(bucket, key):
    """
        Downloads the file given described by the params and parses it.

        Returns a list of L{file_parser.LogLine}s
    """
    s3 = boto3.client('s3')
    with tempfile.NamedTemporaryFile('wb') as local_file:
        s3.download_fileobj(bucket, key, local_file)
        # NOTE: this may cause issues due to processing this file while it's still open. We may
        # need to close the file then process.
        return file_parser.parse_gzipped_file(local_file.name)
