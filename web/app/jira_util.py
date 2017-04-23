import itertools
import logging

from instance import config
import jira

from .jira_issue import JiraIssue


DESCRIPTION_TEMPLATE = '''Error observed in production.

{noformat}
%s
{noformat}

Hits on this error:
%s

More context around this error (from the latest hit):
{noformat}
%s
{noformat}
'''
"""
    A template for the description to save in the ticket.

    Implementer needs to provide:
        - the traceback
        - a list of instances of this traceback
        - a traceback + context text
"""

SIMILAR_LIST_TEMPLATE = ''' - [%s|https://papertrailapp.com/systems/%s/events?focus=%s]'''
"""
    A template for the list of hits on this traceback.

    We list the date of the hit and have that text be a link to the traceback itself.

    Implementer needs to provide:
        - the timestamp of the hit
        - the instance_id of the hit
        - the id of the logline that we want to link to (ie: origin_papertrail_id)
"""

JIRA_CLIENT = jira.JIRA(
    server=config.JIRA_SERVER,
    basic_auth=config.JIRA_BASIC_AUTH,
)
JIRA_PROJECT_KEY = config.JIRA_PROJECT_KEY

logger = logging.getLogger()


def create_title(traceback_text):
    """
        Creates a title for the jira ticket by using the final line of the traceback text
    """
    return traceback_text.splitlines()[-1]


def create_description(similar_tracebacks):
    """
        Creates a description for the JIRA ticket given a collection of tracebacks that share a
        traceback text

        Takes the first traceback as the "master" traceback, from which we get the full context to
        print. This is arbitrary and could be improved in the future by taking the one that user
        selects instead.
    """
    # grab the first as the master, while leaving the "similar" generator intact
    tracebacks, master_traceback_generator = itertools.tee(similar_tracebacks)
    master_traceback = next(master_traceback_generator)

    list_of_tracebacks_string = '\n'.join(
        SIMILAR_LIST_TEMPLATE % (
            t.origin_timestamp,
            t.instance_id,
            t.origin_papertrail_id
        ) for t in tracebacks
    )
    return DESCRIPTION_TEMPLATE % (
        master_traceback.traceback_plus_context_text,
        list_of_tracebacks_string,
        master_traceback.raw_full_text
    )


def create_jira_issue(title, description):
    """
        Creates a issue in jira given the title/description text

        Creates the issue in the project specified by JIRA_PROJECT_KEY.

        Returns the newly created issue
    """
    fields = {
        'project': {'key': JIRA_PROJECT_KEY},
        'summary': title,
        'description': description,
        'issuetype': {'name': 'Bug'},
    }
    issue = JIRA_CLIENT.create_issue(fields=fields)
    logger.info('created jira issue: %s', issue.key)
    return issue


def get_issue(key):
    """
        Get a jira issue given its key

        @rtype: JiraIssue
    """
    try:
        return jira_api_object_to_JiraIssue(JIRA_CLIENT.issue(key))
    except jira.exceptions.JIRAError as e:
        logger.error('error accessing issue %s. is it deleted?\n%s', key, e)


def get_all_issues():
    """
        Get a jira issues.

        Searches for all issues for the configured JIRA_PROJECT_KEY.

        @rtype: generator

        @postcondition: all(isinstance(r, JiraIssue) for r in return)
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
            maxResults=BATCH_SIZE
        )
        if len(new_results) > 0:
            logger.info('got jira issues %s - %s', start_at, start_at + BATCH_SIZE)
            for r in new_results:
                yield r
            start_at += BATCH_SIZE
        else:
            break


def get_link_to_issue(issue):
    """
        Takes a jira issue and returns a URL to that issue

        Returns the user-facing url, not the rest-api one
    """
    assert isinstance(issue, jira.resources.Issue), (type(issue), issue)

    server = config.JIRA_SERVER
    return '%s/browse/%s' % (server, issue.key)


def jira_api_object_to_JiraIssue(jira_object):
    """
        Convert a jira issue object from the jira API to our home-grown JiraIssue class

        @type jira_object: jira.resources.Issue
        @rtype: JiraIssue
    """
    assert isinstance(jira_object, jira.resources.Issue), (type(jira_object), jira_object)

    return JiraIssue(
        jira_object.key,
        get_link_to_issue(jira_object),
        jira_object.fields.summary,
        jira_object.fields.description,
        jira_object.fields.issuetype.name,
        jira_object.fields.status.name,
    )
