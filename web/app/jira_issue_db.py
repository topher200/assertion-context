"""
    Utility functions for performing actions on our ES database of Jira issues

    For all functions, `es` must be an instance of Elasticsearch
"""
from .jira_issue import JiraIssue, generate_from_source
from app import es_util
from app import redis_util



DOGPILE_REGION = redis_util.make_dogpile_region(
    lambda key: "dogpile:jira:" + key
)

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


def remove_jira_issue(es, issue_key):
    """
        Removes any issues with the specified key from the database

        @type issue_key: str
    """
    assert isinstance(issue_key, str), (type(issue_key), issue_key)

    body = {
        "query": {
            "match": {
                "key": {
                    "query": issue_key,
                }
            }
        }
    }
    res = es.delete_by_query(
        index=INDEX,
        doc_type=DOC_TYPE,
        body=body
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
def get_matching_jira_issues(es, traceback_text, match_level):
    """
        Queries the database for any jira issues that include the traceback_text

        We use matching_percentage to determine how much the traceback needs to match the given
        traceback_text before we return it.

        Returns a list (instead of a generator) so we can be cached

        @type traceback_text: str
        @rtype: list

        @precondition: match_level in es_util.ALL_MATCH_LEVELS
        @postcondition: all(isinstance(v, JiraIssue) for v in return)
    """
    assert isinstance(traceback_text, str), (type(traceback_text), traceback_text)
    assert match_level in es_util.ALL_MATCH_LEVELS, (match_level, es_util.ALL_MATCH_LEVELS)

    body = es_util.generate_text_match_payload(
        traceback_text, ["description", "comments"], match_level
    )

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
