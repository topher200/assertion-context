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
        return list(file_parser.parse_gzipped_file(local_file.name))
