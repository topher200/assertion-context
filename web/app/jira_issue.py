import datetime


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
        - the name of the assignee of the issue
        - the current status of the issue
        - the created datetime of the issue
        - the last updated datetime of the issue
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
            assignee,
            status,
            created,
            updated,
    ):
        self._key = key
        self._url = url
        self._summary = summary
        self._description = description
        self._description_filtered = description_filtered
        self._comments = comments
        self._comments_filtered = comments_filtered
        self._issue_type = issue_type
        self._assignee = assignee
        self._status = status
        self._created = created
        self._updated = updated

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
    def assignee(self):
        return self._assignee

    @property
    def status(self):
        return self._status

    @property
    def created(self) -> datetime.datetime:
        return self._created

    @property
    def updated(self) -> datetime.datetime:
        return self._updated

    def document(self) -> dict:
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
            "assignee": self._assignee,
            "status": self._status,
            "created": self._created,
            "updated": self._updated,
        }


def generate_from_source(source:dict) -> JiraIssue:
    """
        L{source} is a dictionary (from ElasticSearch) containing the fields of this object
    """

    created = datetime.datetime.strptime(
        source["created"],
        '%Y-%m-%dT%H:%M:%S.%f%z'

    )
    updated = datetime.datetime.strptime(
        source["updated"],
        '%Y-%m-%dT%H:%M:%S.%f%z'

    )

    return JiraIssue(
        source["key"],
        source["url"],
        source["summary"],
        source["description"],
        source["description_filtered"],
        source["comments"],
        source["comments_filtered"],
        source["issue_type"],
        source["assignee"] if "assignee" in source else '',
        source["status"],
        created,
        updated,
    )
