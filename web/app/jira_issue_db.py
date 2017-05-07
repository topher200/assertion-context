"""
    Utility functions for performing actions on our ES database of Jira issues

    For all functions, `es` must be an instance of Elasticsearch
"""

from dogpile.cache import make_region
import redis

from .jira_issue import JiraIssue, generate_from_source


# if we don't see the remote (docker) redis, see if we're running locally instead
try:
    DOGPILE_REGION = make_region(
        key_mangler=lambda key: "dogpile:jira:" + key
    ).configure(
        'dogpile.cache.redis',
        arguments={
            'host': 'redis',
            'redis_expiration_time': 60*60*2,  # 2 hours
        }
    )
    DOGPILE_REGION.get('confirm_redis_connection')
except redis.exceptions.ConnectionError:
    DOGPILE_REGION = make_region(
        key_mangler=lambda key: "dogpile:jira:" + key
    ).configure(
        'dogpile.cache.redis',
        arguments={
            'host': 'localhost',
            'redis_expiration_time': 60*60*2,  # 2 hours
        }
    )
    DOGPILE_REGION.get('confirm_redis_connection')

INDEX = 'jira-issue-index'
DOC_TYPE = 'jira-issue'


def save_jira_issue(es, jira_issue):
    """
        Saves a jira issue to ES

        Invalidates the dogpile cache

        Returns True if successful

    """
    assert isinstance(jira_issue, JiraIssue), (type(jira_issue), jira_issue)

    doc = jira_issue.document()
    res = es.index(
        index=INDEX,
        doc_type=DOC_TYPE,
        id=jira_issue.key,
        body=doc
    )
    invalidate_cache()
    return res


def invalidate_cache():
    DOGPILE_REGION.invalidate()


def refresh(es):
    """
        Performs an ES refresh. Required to see newly-inserted values when searching
    """
    es.indices.refresh(
        index=INDEX
    )


@DOGPILE_REGION.cache_on_arguments()
def get_matching_jira_issues(es, traceback_text, matching_percentage):
    """
        Queries the database for any jira issues that include the traceback_text

        We use matching_percentage to determine how much the traceback needs to match the given
        traceback_text before we return it.

        Returns a list (instead of a generator) so we can be cached

        @type traceback_text: str
        @rtype: list

        @postcondition: all(isinstance(v, JiraIssue) for v in return)
    """
    assert isinstance(matching_percentage, int), (type(matching_percentage), matching_percentage)

    body = {
        "query": {
            "match": {
                "description": {
                    "query": traceback_text,
                    "slop": 50,
                    "minimum_should_match": "%s%%" % matching_percentage,
                }
            }
        }
    }

    raw_es_response = es.search(
        index=INDEX,
        doc_type=DOC_TYPE,
        body=body,
        size=1000
    )
    res = []
    for raw_jira_issue in raw_es_response['hits']['hits']:
        res.append(generate_from_source(raw_jira_issue['_source']))
    return res
