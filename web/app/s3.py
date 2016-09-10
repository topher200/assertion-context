"""
    Parse a file living on s3
"""
import tempfile

import boto3

import file_parser


def parse_s3_file(bucket, key):
    s3 = boto3.client('s3')
    with tempfile.NamedTemporaryFile('wb', delete=False) as local_file:
        s3.download_fileobj(bucket, key, local_file)
    return file_parser.parse_gzipped_file(local_file.name)