import gzip

from .parser import Parser


def parse_gzipped_file(zipped_filename):
    """
        Opens the gzipped file given by L{zipped_filename} and calls L{parse} on it

        Doesn't perform any checks to confirm that it is a gzip'd file.

        Returns a list of L{Traceback}s
    """
    with gzip.open(zipped_filename, 'rt', encoding='UTF-8') as f:
        return list(Parser.parse_stream(f))
