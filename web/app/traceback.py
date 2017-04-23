import datetime


class Traceback(object):
    """
        L{Traceback} holds the text of many log lines grouped together.

        We parse and filter individual Papertrail log lines to generate the Traceback text.
        Individual Papertrail log lines are combined into a Traceback's L{text} if they share an
        instance_id and program_name in Papertrail.

        Our L{Traceback} contains the knowledge of a "origin" log line. This origin line will be
        the Papertrail line that was used to create very last line in L{text}. We can refer back to
        the original Papertrail log location we generated this Traceback from by referencing the
        origin line's id and timestamp (in L{origin_papertrail_id} and L{origin_timestamp}).

        Fields:
        - traceback_text: the traceback text (only the traceback) parsed from individual log lines.
            no papertrail metadata included - only the parsed 'message' lines from the logs
        - traceback_plus_context_text: the traceback text PLUS an extra few lines before the start
            of the traceback. WARNING: not present in all historical data. will be equal to
            traceback_text if not found
        - raw_traceback_text: the raw traceback text, including Papertrail metadata. no context
            text. WARNING: not present in all historical data. will be equal to traceback_text if
            not found
        - raw_full_text: the raw traceback text, plus many extra lines before the traceback.
            includes Papertrail metadata
        - origin_papertrail_id: the int id papertrail gave the last log line in our traceback.
            assumed to be unique among all other Papertrail ids. example: 700594297938165774
        - origin_timestamp: datetime object (parsed from string) of the timestamp the final log
            line in the Traceback. in utc. example: 2016-08-12T03:18:39
        - instance_id: string of the parsed EC2 instance id. all our log lines shared the same
            instance_id. example: i-2ee330b7
        - program_name: string of the parsed program name. all our log lines shared the same
            program name. example: manager.debug
    """
    def __init__(
            self,
            traceback_text,
            traceback_plus_context_text,
            raw_traceback_text,
            raw_full_text,
            origin_papertrail_id,
            origin_timestamp,
            instance_id,
            program_name,
    ):
        assert isinstance(origin_timestamp, datetime.datetime), (
            type(origin_timestamp), origin_timestamp
        )

        self._traceback_text = traceback_text
        self._traceback_plus_context_text = traceback_plus_context_text
        self._raw_traceback_text = raw_traceback_text
        self._raw_full_text = raw_full_text
        self._origin_papertrail_id = origin_papertrail_id
        self._origin_timestamp = origin_timestamp
        self._instance_id = instance_id
        self._program_name = program_name

    def document(self):
        """
            Returns the document form of this logline for ElasticSearch.

            Document form is a dictionary of <field name>: <value> pairs.
        """
        return {
            "traceback_text": self._traceback_text,
            "traceback_plus_context_text": self._traceback_plus_context_text,
            "raw_traceback_text": self._raw_traceback_text,
            "raw_full_text": self._raw_full_text,
            "origin_papertrail_id": self._origin_papertrail_id,
            "origin_timestamp": self._origin_timestamp,
            "instance_id": self._instance_id,
            "program_name": self._program_name,
        }

    def __repr__(self):
        return str(self.document())

    @property
    def traceback_text(self):
        return self._traceback_text

    @property
    def traceback_plus_context_text(self):
        # not guaranteed to exist
        if self._traceback_plus_context_text is not None:
            return self._traceback_plus_context_text
        else:
            return self.traceback_text

    @property
    def raw_traceback_text(self):
        # not guaranteed to exist
        if self._raw_full_text is not None:
            return self._raw_full_text
        else:
            return self.traceback_text

    @property
    def raw_full_text(self):
        return self._raw_full_text

    @property
    def origin_papertrail_id(self):
        return self._origin_papertrail_id

    @property
    def origin_timestamp(self):
        return self._origin_timestamp

    @property
    def instance_id(self):
        return self._instance_id

    @property
    def program_name(self):
        return self._program_name


def generate_traceback_from_source(source):
    """
        L{source} is a dictionary (from ElasticSearch) containing the fields of a L{Traceback}
    """
    assert isinstance(source, dict), (type(source), source)

    # We get the datetime as a string, we need to parse it out
    try:
        timestamp = datetime.datetime.strptime(
            source["origin_timestamp"],
            '%Y-%m-%dT%H:%M:%S%z'
        )
    except ValueError:
        # no timezone info on this one
        timestamp = datetime.datetime.strptime(
            source["origin_timestamp"],
            '%Y-%m-%dT%H:%M:%S'
        )

    return Traceback(
        source["traceback_text"],
        source.get("traceback_plus_context_text", None),  # not guaranteed to exist
        source.get("raw_traceback_text", None),  # not guaranteed to exist
        source.get("raw_full_text", 'raw_text'),  # original name was 'raw_text'
        source["origin_papertrail_id"],
        timestamp,
        source["instance_id"],
        source["program_name"],
    )
