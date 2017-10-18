import datetime


class ApiCall(object):
    """
        ApiCall is a single RPC-style call to Engine or Manager.

        We log how long the call took and other useful information.

        - parsed_log_message: string containing the parsed log message without any metadata
        - raw_log_message: string containing the original message as found in papertrail. note that
            we re-create the message in this format inside our parser so that we match what
            users see in the web UI
        - timestamp: datetime object (parsed from string) of the timestamp the message was created.
            in utc. example: 2016-08-12T03:18:39
        - papertrail_id: the int id papertrail gave the log line. assumed to be unique. example:
            700594297938165774
        - instance_id: string of the parsed EC2 instance id of the log line
        - program_name: string of the parsed program name from the log line.
            example: 'aws1.engine.server.debug'
        - api_name: string of the parsed API name from the log line
            example: 'IsGetInProgressHandler'
        - profile_name: profile name of the user who made the api call
        - username: user name of the user who made the api call
        - method: REST API method of the call. example: 'GET'
        - duration: time in ms that the API call took
    """
    def __init__(
            self,
            parsed_log_message,
            raw_log_message,
            timestamp,
            papertrail_id,
            instance_id,
            program_name,
            api_name,
            profile_name,
            username,
            method,
            duration
    ):
        self._parsed_log_message = parsed_log_message
        self._raw_log_message = raw_log_message
        self._timestamp = timestamp
        self._papertrail_id = papertrail_id
        self._instance_id = instance_id
        self._program_name = program_name
        self._api_name = api_name
        self._profile_name = profile_name
        self._username = username
        self._method = method
        self._duration = duration

    def document(self):
        """
            Returns the document form of this entity for ElasticSearch.

            Document form is a dictionary of <field name>: <value> pairs.
        """
        return {
            "parsed_log_message": self._parsed_log_message,
            "raw_log_message": self._raw_log_message,
            "timestamp": self._timestamp.strftime('%Y-%m-%dT%H:%M:%S%z'),
            "papertrail_id": self._papertrail_id,
            "instance_id": self._instance_id,
            "program_name": self._program_name,
            "api_name": self._api_name,
            "profile_name": self._profile_name,
            "username": self._username,
            "method": self._method,
            "duration": self._duration,
        }

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.document())

    @staticmethod
    def generate_from_source(source):
        """
            L{source} is a dictionary (from ElasticSearch) containing the fields of this entity
        """
        assert isinstance(source, dict), source

        # We get the datetime as a string, we need to parse it out
        timestamp = datetime.datetime.strptime(
            source["origin_timestamp"],
            '%Y-%m-%dT%H:%M:%S%z'
        )

        return ApiCall(
            source["parsed_log_message"],
            source["raw_log_message"],
            timestamp,
            source["papertrail_id"],
            source["instance_id"],
            source["program_name"],
            source["api_name"],
            source["profile_name"],
            source["username"],
            source["method"],
            source["duration"],
        )

    @property
    def parsed_log_message(self):
        return self._parsed_log_message

    @property
    def raw_log_message(self):
        return self._raw_log_message

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def papertrail_id(self):
        return self._papertrail_id

    @property
    def instance_id(self):
        return self._instance_id

    @property
    def program_name(self):
        return self._program_name

    @property
    def api_name(self):
        return self._api_name

    @property
    def profile_name(self):
        return self._profile_name

    @property
    def username(self):
        return self._username

    @property
    def method(self):
        return self._method

    @property
    def duration(self):
        return self._duration
