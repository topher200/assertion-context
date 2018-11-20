# pylint: disable=line-too-long
import logging
import re
from typing import (
    Iterator,
    Optional,
)

import jira

from . import (
    config_util,
    jira_issue_db,
    traceback_formatter,
)
from .jira_issue import JiraIssue

logger = logging.getLogger()

JIRA_SERVER=config_util.get('JIRA_SERVER')
JIRA_BASIC_AUTH_USERNAME=config_util.get('JIRA_BASIC_AUTH_USERNAME')
JIRA_BASIC_AUTH_PASSWORD=config_util.get('JIRA_BASIC_AUTH_PASSWORD')
JIRA_PROJECT_KEY=config_util.get('JIRA_PROJECT_KEY')

JIRA_ASSIGNEE_ADWORDS = config_util.get('JIRA_ASSIGNEE_ADWORDS')
JIRA_ASSIGNEE_BING = config_util.get('JIRA_ASSIGNEE_BING')
JIRA_ASSIGNEE_SOCIAL = config_util.get('JIRA_ASSIGNEE_SOCIAL')
JIRA_ASSIGNEE_GRADER = config_util.get('JIRA_ASSIGNEE_GRADER')

DESCRIPTION_TEMPLATE = '''Error observed in production.

{noformat}
%s
{noformat}

Hits on this error:
%s
'''
"""
    A template for the description to save in the ticket.

    Implementer needs to provide:
        - the traceback
        - a list of instances of this traceback
"""

COMMENT_TEMPLATE = '''Errors observed in production:
%s
'''
"""
    A template for the comment containing a list of recent hits

    Implementer needs to provide:
        - a list of instances of this traceback
"""

__JIRA_CLIENT_SINGLETON = None
def JiraClient():
    global __JIRA_CLIENT_SINGLETON
    if __JIRA_CLIENT_SINGLETON is None:
        # can thrown requests.exceptions.SSLError
        __JIRA_CLIENT_SINGLETON = jira.JIRA(
            server=JIRA_SERVER,
            basic_auth=(JIRA_BASIC_AUTH_USERNAME, JIRA_BASIC_AUTH_PASSWORD),
        )
    return __JIRA_CLIENT_SINGLETON

JIRA_PROJECT_KEY = JIRA_PROJECT_KEY

COMMENT_SEPARATOR = '\n!!!newcomment!!!\n'
"""
    We're saving comments in the database as one long string. This is the separator between them
"""

logger = logging.getLogger()


class UnknownTeamNameError(Exception):
    pass
class AssignToTeam():
    """
        AssignToTeam holds which team to assign a ticket to
    """
    def __init__(self, team_name):
        if team_name not in (
            'UNASSIGNED',
            'ADWORDS',
            'BING',
            'SOCIAL',
            'GRADER',
        ):
            raise UnknownTeamNameError(team_name)
        self.team_name = team_name

    def __repr__(self):
        return 'Assign to %s' % self.team_name

    def __eq__(self, other):
        return self.team_name == other.team_name


def create_title(traceback_text):
    """
        Intelligently creates a title for the jira ticket

        If the final line of the traceback has some substance (defined as being more than one
        word), we use the last line. Otherwise, we combine the last line and the second-to-last
        line.
    """
    try:
        last_line = traceback_text.splitlines()[-1].strip()
        second_to_last_line = traceback_text.splitlines()[-2].strip()
    except IndexError:
        logger.warning('traceback text as fewer lines than expected')
        return 'Error: Bad Jira title'

    if len(last_line) > 250:
        # jira has a title limit of 250. use the second-to-last line instead
        return second_to_last_line
    elif len(last_line.split()) > 1:
        # last line is good (has more than one word). let's use it!
        return last_line
    else:
        # last line is too short, combine it with the second-to-last line
        return '%s: %s' % (last_line, second_to_last_line)


def create_description(similar_tracebacks):
    """
        Creates a description for the JIRA ticket given a collection of tracebacks that share a
        traceback text

        Takes the first traceback as the "master" traceback, from which we get the full context to
        print. This is arbitrary and could be improved in the future by taking the one that user
        selects instead.
    """
    tracebacks = list(similar_tracebacks)
    assert tracebacks, tracebacks
    # grab the first as the master
    master_traceback = tracebacks[0]

    return DESCRIPTION_TEMPLATE % (
        master_traceback.traceback_plus_context_text.rstrip(),
        traceback_formatter.create_hits_list(tracebacks, traceback_formatter.jira_formatted_string)
    )


def create_comment_with_hits_list(tracebacks):
    """
        Creates a comment given the list of tracebacks

        Sorts them so that the latest one is first. Only takes the 50 latest.
    """
    tracebacks.sort(key=lambda tb: int(tb.origin_papertrail_id), reverse=True)
    return COMMENT_TEMPLATE % (
        traceback_formatter.create_hits_list(tracebacks[:50], traceback_formatter.jira_formatted_string)
    )


def create_comment(issue, comment_string):
    """
        Leaves the given comment on the issue
    """
    JiraClient().add_comment(issue.key, comment_string)
    logger.info('added comment to issue: %s', issue.key)


def create_jira_issue(title:str, description:str, assign_to:AssignToTeam) -> str:
    """
        Creates a issue in jira given the title/description text

        Creates the issue in the project specified by JIRA_PROJECT_KEY.

        Returns the newly created issue

        @return: the key of the newly created issue
    """
    fields = {
        'project': {'key': JIRA_PROJECT_KEY},
        'summary': title,
        'description': description,
        'issuetype': {'name': 'Bug'},
        'priority': {'name': 'Critical'},
        'labels': ['tracebacks'],
    }

    if assign_to == AssignToTeam('UNASSIGNED'):
        assignee = None
        component = None
    elif assign_to == AssignToTeam('ADWORDS'):
        assignee = JIRA_ASSIGNEE_ADWORDS
        component = 'Manage PPC'
    elif assign_to == AssignToTeam('BING'):
        assignee = JIRA_ASSIGNEE_BING
        component = 'Manage PPC'
    elif assign_to == AssignToTeam('SOCIAL'):
        assignee = JIRA_ASSIGNEE_SOCIAL
        component = 'Social'
        # epic links are set strangely. this value will not carry over to different Jiras
        # see https://community.atlassian.com/t5/Answers-Developer-Questions/Link-to-Epic-in-rest-api-issue-resource/qaq-p/562851
        fields['customfield_10008'] = 'PPC-13290'
    elif assign_to == AssignToTeam('GRADER'):
        assignee = JIRA_ASSIGNEE_GRADER
        component = 'Grader'
    if assignee:
        fields['assignee'] = {'name': assignee}
        fields['components'] = [{'name': component}] # type: ignore # jira API is weird

    issue = JiraClient().create_issue(fields=fields)
    return issue.key


def get_issue(key:str) -> Optional[JiraIssue]:
    """
        Get a jira issue given its key

        Returns None if we can't find the given issue. This can happen if a user deletes an issue
        in Jira

        @rtype: JiraIssue or None
    """
    try:
        return jira_api_object_to_JiraIssue(JiraClient().issue(key))
    except jira.exceptions.JIRAError as e:
        logger.warning('failure accessing issue %s. is it deleted?\n%s', key, e)
        return None


def get_all_issues() -> Iterator[jira.resources.Issue]:
    """
        Get a jira issues.

        Searches for all issues for the configured JIRA_PROJECT_KEY.

        Returns issues in the jira API object form, not our home-grown JiraIssue form.

        Only grabs the 'id' field of the jira issues, since that's all we're currently using
    """
    # there seems to be a bug in the jira library where it only grabs the first 50 results (even if
    # maxResults evaluates to False, as instructed to do by the docs). we'll handle the pagination
    # ourselves.
    start_at = 0
    BATCH_SIZE = 50
    while True:
        new_results = JiraClient().search_issues(
            'project=%s' % JIRA_PROJECT_KEY,
            startAt=start_at,
            maxResults=BATCH_SIZE,
            fields='key'
        )
        if new_results:
            logger.info('got jira issues %s - %s', start_at, start_at + BATCH_SIZE)
            for r in new_results:
                yield r
            start_at += BATCH_SIZE
        else:
            break


def search_matching_jira_tickets(ES, search_phrase:str) -> Iterator[dict]:
    """
        Get the top Jira issues that match the given search phrase.

        Yields dicts, with each dict a text/value pair that refers to a Jira issue:
        - text: the display summary of the jira issue, in this form: "KEY, STATUS: SUMMARY"
        - value: the key of the jira issue
    """
    for issue in jira_issue_db.search_jira_issues(ES, search_phrase, max_count=30):
        yield {
            "text": "%s: %s" % (issue.key, issue.summary),
            "value": issue.key,
        }


def get_link_to_issue(issue_key:str) -> str:
    """
        Takes a jira issue key and returns a URL to that issue

        Returns the user-facing url, not the rest-api one
    """
    assert isinstance(issue_key, str), (type(issue_key), issue_key)

    server = JIRA_SERVER
    return '%s/browse/%s' % (server, issue_key)


def jira_api_object_to_JiraIssue(jira_object:jira.resources.Issue) -> JiraIssue:
    """
        Convert a jira issue object from the jira API to our home-grown JiraIssue class
    """
    assert isinstance(jira_object, jira.resources.Issue), (type(jira_object), jira_object)

    comments = (comment.body for comment in jira_object.fields.comment.comments)
    comments_text = COMMENT_SEPARATOR.join(comments)

    description = jira_object.fields.description
    description_filtered = __strip_papertrail_metadata(description)
    comments_filtered = __strip_papertrail_metadata(comments_text)

    return JiraIssue(
        jira_object.key,
        get_link_to_issue(jira_object.key),
        jira_object.fields.summary,
        description,
        description_filtered,
        comments_text,
        comments_filtered,
        jira_object.fields.issuetype.name,
        jira_object.fields.assignee.displayName,
        jira_object.fields.status.name,
        jira_object.fields.created,
        jira_object.fields.updated,
    )


def get_all_referenced_ids(issue:JiraIssue) -> Iterator[int]:
    """
        Look through the comments and description and find all papertrail ids that are referenced.

        Note that we might yield the same ID more than once.

        @return: yields individual ids as ints
    """
    # look for the 'old' pattern, which is what you get when you copy/paste from papertrail
    pattern = '(?:focus|centered_on_id)=(\d{18})'
    for match in re.findall(pattern, issue.description):
        yield int(match)
    for match in re.findall(pattern, issue.comments):
        yield int(match)

    # look for my super fancy new pattern. we could make these be one check, but this is simpler
    pattern = 'traceback/(\d{18})'
    for match in re.findall(pattern, issue.description):
        yield int(match)
    for match in re.findall(pattern, issue.comments):
        yield int(match)


def find_latest_referenced_id(issue:JiraIssue) -> Optional[int]:
    """
        Look through the comments and description find the latest papertrail id someone referenced

        @return: a single papertrail id or None if no ids are found
    """
    assert isinstance(issue, JiraIssue), (type(issue), issue)

    return max(get_all_referenced_ids(issue), default=None) # type: ignore # not sure why mypy barfs


def __strip_papertrail_metadata(text:str) -> str:
    """
        Given a block of text, filters out papertrail metadata

        Filtering happens in two steps:
        1. Find all the tracebacks in the text. Find the instance ids of those tracebacks. Strip
        out any papertrail log lines that aren't from one of those instances - these are log lines
        that aren't part of a traceback and they're just noise.
        2. Strip all papertrail metadata from all lines

        The result of this function should leave any tracebacks that were copy/pasted out of
        papertrail as just the traceback text, without any metadata or extranious lines.

        @rtype: str
    """
    if not text:
        return ''

    matches = re.findall(__GET_INSTANCE_ID_AND_PROGRAM_NAME_REGEX, text)
    lines_to_keep = []
    for line in text.splitlines():
        keep = False
        if re.search(__PAPERTRAIL_METADATA_REGEX, line):
            # it's a papertrail line - see if we should keep it
            for instance_id, program_name in matches:
                if instance_id in line and program_name in line:
                    keep = True
        else:
            # always keep non-papertrail lines
            keep = True
        if keep:
            lines_to_keep.append(line)
    result_text = '\n'.join(lines_to_keep)

    return re.sub(__PAPERTRAIL_METADATA_REGEX, '', result_text)


__GET_INSTANCE_ID_AND_PROGRAM_NAME_REGEX = re.compile(
    '\w{3} \d{2} \d\d:\d\d:\d\d (i-\w+) (\S+):.*Traceback \(most recent call last\):'
)
"""
    Regex that matches on the Traceback line from a set of text.

    Produces the AWS instance id and program name as a match group tuple
"""


__PAPERTRAIL_METADATA_REGEX = re.compile('\w{3} \d{2} \d\d:\d\d:\d\d i-\w+ \S+:')
"""
    Regex that matches on the papertrail metadata on a line

    On the line...
        Apr 18 11:19:55 i-00cb37cd49bdd7b66 aws1.engine.server: assert (not code) != (not error)
    this would match on...
        Apr 18 11:19:55 i-00cb37cd49bdd7b66 aws1.engine.server:
"""
