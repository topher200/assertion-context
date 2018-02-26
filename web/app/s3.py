"""
    Parse a file living on s3
"""
import logging
import tempfile

import boto3
import botocore

from . import config_util
from . import file_parser
from . import retry


logger = logging.getLogger()

AWS_REGION = config_util.get('AWS_REGION')
AWS_ACCESS_KEY_ID = config_util.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config_util.get('AWS_SECRET_ACCESS_KEY')


@retry.Retry(exceptions=(EOFError,))
def parse_s3_file(bucket, key):
    """
        Downloads the file given described by the params and parses it.

        Returns a list of L{Traceback}s and a list of L{ApiCall}. Returns None, None on error.
    """
    s3 = boto3.client(
        's3',
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    with tempfile.NamedTemporaryFile('wb') as local_file:
        try:
            s3.download_fileobj(bucket, key, local_file)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '403':
                logger.warning("'403 Forbidden' error when trying to download from s3")
                logger.warning(
                    "This happens when the system clock is out of date. Restart the container."
                )
                return None, None
            elif e.response['Error']['Code'] == '404':
                logger.info("'404 Not Found' error when trying to download from s3")
                logger.info("Check your filename")
                return None, None
            logger.error("failed to download file from s3 with unknown error")
            raise
        return file_parser.parse_gzipped_file(local_file.name)
