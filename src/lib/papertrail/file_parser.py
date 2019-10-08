import gzip

from lib.api_call.api_call_parser import ApiCallParser
from lib.traceback.parser import Parser


def parse_gzipped_file(zipped_filename):
    """
        Opens the gzipped file given by L{zipped_filename} and calls L{parse} on it

        Doesn't perform any checks to confirm that it is a gzip'd file.

        Returns a list of L{Traceback} and a list of L{ApiCall}
    """
    with gzip.open(zipped_filename, 'rt', encoding='UTF-8') as f:
        tracebacks = list(Parser.parse_stream(f))

    with gzip.open(zipped_filename, 'rt', encoding='UTF-8') as f:
        api_calls = list(ApiCallParser.parse_stream(f))

    return tracebacks, api_calls
