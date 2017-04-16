import itertools
import logging

from instance import config
import jira


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
        master_traceback.traceback_text,
        list_of_tracebacks_string,
        master_traceback.raw_text
    )


def create_jira_issue(title, description):
    """
        Creates a issue in jira given the title/description text

        Returns the newly created issue
    """
    fields = {
        'project': {'key': 'SAN'},
        'summary': title,
        'description': description,
        'issuetype': {'name': 'Bug'},
    }
    issue = JIRA_CLIENT.create_issue(fields=fields)
    logger.info('created jira issue: %s', issue.key)
    return issue

def get_link_to_issue(issue):
    """
        Takes a jira issue and returns a URL to that issue

        Returns the user-facing url, not the rest-api one
    """
    server = config.JIRA_SERVER
    return '%s/browse/%s' % (server, issue.key)
