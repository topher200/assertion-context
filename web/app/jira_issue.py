class JiraIssue():
    """
        Object representing a JIRA issue.

        We save the following fields:
        - The key JIRA gives the issue. For example: PPC-123
        - url of the issue
        - The summary of the issue. The "title" of the ticket
        - description text
        - description text, with any papertrail metadata filtered out
        - string of all the issue's comments, concatinated together
        - string of all the issue's comments, concatinated together, with any papertrail metadata
          filtered out
        - the type of the issue (bug, story, etc)
        - the current status of the issue
    """
    def __init__(
            self,
            key,
            url,
            summary,
            description,
            description_filtered,
            comments,
            comments_filtered,
            issue_type,
            status,
    ):
        self._key = key
        self._url = url
        self._summary = summary
        self._description = description
        self._description_filtered = description_filtered
        self._comments = comments
        self._comments_filtered = comments_filtered
        self._issue_type = issue_type
        self._status = status

    def __repr__(self):
        return str(self.document())

    @property
    def key(self):
        return self._key

    @property
    def url(self):
        return self._url

    @property
    def summary(self):
        return self._summary

    @property
    def description(self):
        return self._description

    @property
    def description_filtered(self):
        return self._description_filtered

    @property
    def comments(self):
        return self._comments

    @property
    def comments_filtered(self):
        return self._comments_filtered

    @property
    def issue_type(self):
        return self._issue_type

    @property
    def status(self):
        return self._status

    def document(self):
        """
            Returns the document form of this object for ElasticSearch.

            Document form is a dictionary of <field name>: <value> pairs.
        """
        return {
            "key": self._key,
            "url": self._url,
            "summary": self._summary,
            "description": self._description,
            "description_filtered": self._description_filtered,
            "comments": self._comments,
            "comments_filtered": self._comments_filtered,
            "issue_type": self._issue_type,
            "status": self._status,
        }


def generate_from_source(source):
    """
        L{source} is a dictionary (from ElasticSearch) containing the fields of this object
    """
    assert isinstance(source, dict), (type(source), source)

    return JiraIssue(
        source["key"],
        source["url"],
        source["summary"],
        source["description"],
        source["description_filtered"],
        source["comments"],
        source["comments_filtered"],
        source["issue_type"],
        source["status"],
    )
