import gzip
import logging
import json

from .parser import Parser


logger = logging.getLogger()


def parse_json_stream(stream):
    """
        Yields Tracebacks from a papertrail-cli JSON stream

        The JSON stream takes the form of many parsed log lines in a JSON list. For example, one
        line may look like this:
        {
            "id":"824915807000000009",
            "source_ip":"100.88.888.888",
            "program":"update.debug",
            "message":"    return self.do_stuff(fields, params)",
            "received_at":"2017-07-21T00:47:57-04:00",
            "generated_at":"2017-07-21T00:47:57-04:00",
            "display_received_at":"Jul 21 00:47:57",
            "source_id":1025470000,
            "source_name":"i-0935000000000000c",
            "hostname":"i-0935a00000000000c",
            "severity":"Notice",
            "facility":"User"
        }
    """
    yield from Parser.parse_stream(yield_lines(stream))


def yield_lines(stream):
    """
        Takes a stream of events from 'papertrail-cli -f' and turns them into log lines.

        Log lines here is defined as the format of lines from the gzip'd archives that papertrail
        makes.

        Each line in the stream is a JSON dump of a bunch of log events. We piece it all together
        into just a stream of text log lines.
    """
    for dump in stream:
        for event in json.loads(dump)['events']:
            yield '\t'.join([
                str(event['id']),
                event['generated_at'],
                event['received_at'],
                str(event['source_id']),
                event['source_name'],
                event['source_ip'],
                event['facility'],
                event['severity'],
                event['program'],
                event['message'],
            ])
