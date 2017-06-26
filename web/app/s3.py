"""
    Parse a file living on s3
"""
import logging
import tempfile

import boto3
import botocore

from . import file_parser
from . import retry


logger = logging.getLogger()


@retry.Retry(exceptions=(EOFError,))
def parse_s3_file(bucket, key):
    """
        Downloads the file given described by the params and parses it.

        Returns a list of L{Traceback}s. Returns None on error.
    """
    s3 = boto3.client('s3')
    with tempfile.NamedTemporaryFile('wb') as local_file:
        try:
            s3.download_fileobj(bucket, key, local_file)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '403':
                logger.warning("'403 Forbidden' error when trying to download from s3")
                logger.warning(
                    "This happens when the system clock is out of date. Restart the container."
                )
                return None
            elif e.response['Error']['Code'] == '404':
                logger.info("'404 Not Found' error when trying to download from s3")
                logger.info("Check your filename")
                return None
            logger.error("failed to download file from s3 with unknown error")
            raise
        return file_parser.parse_gzipped_file(local_file.name)
