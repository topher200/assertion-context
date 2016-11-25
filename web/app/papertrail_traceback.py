class PapertrailTraceback(object):
    """
        L{PapertrailTraceback} holds the text for a single traceback from papertrail
    """
    def __init__(
            self,
            timestamp,
            origin_papertrail_id,
            text,
    ):
        self._timestamp = timestamp
        self._origin_papertrail_id = origin_papertrail_id
        self._text = text

    def document(self):
        """
            Returns the document form of this Traceback for ElasticSearch.

            Document form is a dictionary of <field name>: <value> pairs.
        """
        return {
            "timestamp": self._timestamp,
            "origin_papertrail_id": self._origin_papertrail_id,
            "text": self._text,
        }

    def __repr__(self):
        return str(self.document())

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def origin_papertrail_id(self):
        return self._origin_papertrail_id

    @property
    def text(self):
        return self._text
