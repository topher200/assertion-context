from .traceback import Traceback


JIRA_STRING_TEMPLATE = ''' - [%s|https://papertrailapp.com/systems/%s/events?focus=%s]'''
"""
    A template for the list of hits on this traceback for jira.

    We list the date of the hit and have that text be a link to the traceback itself.

    Implementer needs to provide:
        - the timestamp of the hit
        - the instance_id of the hit
        - the id of the logline that we want to link to (ie: origin_papertrail_id)
"""

TIMESTAMP_TEMPLATE = '%b %d %Y %H:%M:%S'
"""
    A template for human-readable timestamps. Timezone info is ignored.

    To be used by datetime a datetime object like this: `dt.strftime(TIMESTAMP_TEMPLATE)`
"""

def human_readable_string(traceback: Traceback) -> str:
    """ Given a traceback, returns a well formatted string for presentation """
    pass


def jira_formatted_string(t: Traceback) -> str:
    """ Given a traceback, returns a wall formatting string in Jira's bad formatting """
    return JIRA_STRING_TEMPLATE % (
        t.origin_timestamp.strftime(TIMESTAMP_TEMPLATE),
        t.instance_id,
        t.origin_papertrail_id
    )
