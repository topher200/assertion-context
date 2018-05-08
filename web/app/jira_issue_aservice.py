# pylint: disable=line-too-long
import logging
import re

import jira

from . import (
    config_util,
    traceback_formatter,
)
from .jira_issue import JiraIssue


JIRA_SERVER=config_util.get('JIRA_SERVER')
JIRA_BASIC_AUTH_USERNAME=config_util.get('JIRA_BASIC_AUTH_USERNAME')
JIRA_BASIC_AUTH_PASSWORD=config_util.get('JIRA_BASIC_AUTH_PASSWORD')
JIRA_PROJECT_KEY=config_util.get('JIRA_PROJECT_KEY')

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

JIRA_CLIENT = jira.JIRA(
    server=JIRA_SERVER,
    basic_auth=(JIRA_BASIC_AUTH_USERNAME, JIRA_BASIC_AUTH_PASSWORD),
)
JIRA_PROJECT_KEY = JIRA_PROJECT_KEY

COMMENT_SEPARATOR = '\n!!!newcomment!!!\n'
"""
    We're saving comments in the database as one long string. This is the separator between them
"""

logger = logging.getLogger()


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
        create_jira_hits_list(tracebacks)
    )


def create_comment_with_hits_list(tracebacks):
    """
        Creates a comment given the list of tracebacks

        Sorts them so that the latest one is first
    """
    tracebacks.sort(key=lambda tb: int(tb.origin_papertrail_id), reverse=True)
    return COMMENT_TEMPLATE % (create_jira_hits_list(tracebacks))


def create_jira_hits_list(tracebacks):
    """
        Creates a well formatted list of strings, given a list of tracebacks

        Jira has a limit of 32767 characters per comment. We will try to keep it under 25000.
    """
    seen_profile_names = set()
    seen_usernames = set()
    hits_list = []
    for t in tracebacks:
        # if it's the first time seeing this profile or username, include links to them
        if t.profile_name not in seen_profile_names:
            include_profile_link = True
            seen_profile_names.add(t.profile_name)
        else:
            include_profile_link = False
        if t.username not in seen_usernames:
            include_username_link = True
            seen_usernames.add(t.username)
        else:
            include_username_link = False

        # don't include links to admin users
        if t.username and t.username.startswith('@'):
            include_username_link = False

        hits_list.append(traceback_formatter.jira_formatted_string(t, include_profile_link, include_username_link))

    # keep trying fewer and fewer comments until we fit
    index = len(hits_list)
    for index in range(index, 0, -1):
        comment_string = '\n'.join(hits_list[:index])
        if len(comment_string) < 25000:
            break

    logger.info(
        'for %s tracebacks, built %s hits and took the first %s for a %s char comment',
        len(tracebacks), len(hits_list), index, len(comment_string)
    )

    return comment_string


def create_comment(issue, comment_string):
    """
        Leaves the given comment on the issue
    """
    JIRA_CLIENT.add_comment(issue.key, comment_string)
    logger.info('added comment to issue: %s', issue.key)


def create_jira_issue(title, description):
    """
        Creates a issue in jira given the title/description text

        Creates the issue in the project specified by JIRA_PROJECT_KEY.

        Returns the newly created issue

        @rtype: jira.resources.Issue
    """
    fields = {
        'project': {'key': JIRA_PROJECT_KEY},
        'summary': title,
        'description': description,
        'issuetype': {'name': 'Bug'},
        'labels': ['tracebacks'],
    }
    issue = JIRA_CLIENT.create_issue(fields=fields)
    logger.info('created jira issue: %s', issue.key)
    return issue


def get_issue(key):
    """
        Get a jira issue given its key

        Returns None if we can't find the given issue. This can happen if a user deletes an issue
        in Jira

        @rtype: JiraIssue or None
    """
    try:
        return jira_api_object_to_JiraIssue(JIRA_CLIENT.issue(key))
    except jira.exceptions.JIRAError as e:
        logger.warning('failure accessing issue %s. is it deleted?\n%s', key, e)
        return None


def get_all_issues():
    """
        Get a jira issues.

        Searches for all issues for the configured JIRA_PROJECT_KEY.

        Returns issues in the jira API object form, not our home-grown JiraIssue form.

        Only grabs the 'id' field of the jira issues, since that's all we're currently using

        @rtype: generator

        @postcondition: all(isinstance(r, jira.resources.Issue) for r in return)
    """
    # there seems to be a bug in the jira library where it only grabs the first 50 results (even if
    # maxResults evaluates to False, as instructed to do by the docs). we'll handle the pagination
    # ourselves.
    start_at = 0
    BATCH_SIZE = 50
    while True:
        new_results = JIRA_CLIENT.search_issues(
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


def get_link_to_issue(issue_key):
    """
        Takes a jira issue key and returns a URL to that issue

        Returns the user-facing url, not the rest-api one
    """
    assert isinstance(issue_key, str), (type(issue_key), issue_key)

    server = JIRA_SERVER
    return '%s/browse/%s' % (server, issue_key)


def jira_api_object_to_JiraIssue(jira_object):
    """
        Convert a jira issue object from the jira API to our home-grown JiraIssue class

        @type jira_object: jira.resources.Issue
        @rtype: JiraIssue
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
        jira_object.fields.status.name,
    )


def get_all_referenced_ids(issue):
    """
        Look through the comments and description and find all papertrail ids that are referenced

        @type issue: JiraIssue
        @return: yields individual ids as ints
        @rtype: generator
    """
    assert isinstance(issue, JiraIssue), (type(issue), issue)

    pattern = '(?:focus|centered_on_id)=(\d{18})'
    for match in re.findall(pattern, issue.description):
        yield int(match)
    for match in re.findall(pattern, issue.comments):
        yield int(match)


def find_latest_referenced_id(issue):
    """
        Look through the comments and description find the latest papertrail id someone referenced

        @type issue: JiraIssue
        @return: a single papertrail id or None if no ids are found
        @rtype: int or None
    """
    assert isinstance(issue, JiraIssue), (type(issue), issue)

    return max(get_all_referenced_ids(issue), default=None)


def __strip_papertrail_metadata(text):
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
