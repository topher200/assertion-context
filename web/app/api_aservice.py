# AService functions for performing our most high-level API actions

import datetime
import logging

import flask
import opentracing
import pytz

from opentracing_instrumentation.request_context import get_current_span, span_in_context

from app import (
    es_util,
    jira_issue_db,
    tasks,
    text_keys,
    traceback_database,
)

logger = logging.getLogger()


class TracebackPlusMetadata():
    """
        A lightweight class to hold a Traceback plus some metadata.

        We made a class (instead of a namedtuple) so that we can build incrementally.
    """
    def __init__(self, traceback):
        self.traceback = traceback

    __slots__ = [
        'traceback',
        'jira_issues',
        'similar_jira_issues',
        'similar_tracebacks',
    ]


def get_tracebacks_for_day(
        ES, tracer, date_to_analyze:datetime.date, filter_text:str
) -> TracebackPlusMetadata:
    """
        Retrieves the Tracebacks for the given date_to_analyze date.

        If provided, only returns Tracebacks which match filter_text.
    """
    tracer = tracer or opentracing.tracer
    root_span = get_current_span()

    # get all tracebacks
    with tracer.start_span('get all tracebacks', child_of=root_span) as span:
        with span_in_context(span):
            tracebacks = traceback_database.get_tracebacks(ES, tracer, date_to_analyze, date_to_analyze)
    logger.debug('found %s tracebacks', len(tracebacks))

    # create a set of tracebacks that match all the traceback texts the user has hidden
    with tracer.start_span('determine hidden tracebacks', child_of=root_span) as span:
        with span_in_context(span):
            hidden_tracebacks = set()
            if flask.session.get(text_keys.HIDDEN_TRACEBACK) is not None:
                for traceback_text in flask.session.get(text_keys.HIDDEN_TRACEBACK):
                    for tb in traceback_database.get_matching_tracebacks(
                            ES, tracer, traceback_text, es_util.EXACT_MATCH, 10000
                    ):
                        hidden_tracebacks.add(tb.origin_papertrail_id)
                logger.info('found %s traceback ids we need to hide', len(hidden_tracebacks))

    # filter out tracebacks the user has hidden. we use a namedlist to store each traceback + some
    # metadata we'll use when rendering the html page
    tb_meta = [
        TracebackPlusMetadata(traceback=t) for t in tracebacks
        if t.origin_papertrail_id not in hidden_tracebacks
    ]

    # get a list of matching jira issues
    with tracer.start_span('get matching jira issues', child_of=root_span) as span:
        with span_in_context(span):
            for tb in tb_meta:
                tb.jira_issues = jira_issue_db.get_matching_jira_issues(
                    ES, tracer, tb.traceback.traceback_text, es_util.EXACT_MATCH
                )
                matching_jira_keys = set(jira_issue.key for jira_issue in tb.jira_issues)
                similar_jira_issues = jira_issue_db.get_matching_jira_issues(
                    ES, tracer, tb.traceback.traceback_text, es_util.SIMILAR_MATCH
                )
                tb.similar_jira_issues = [similar_jira_issue for similar_jira_issue in similar_jira_issues
                                        if similar_jira_issue.key not in matching_jira_keys]

    # apply user's filters
    if filter_text == 'Has Ticket':
        tb_meta = [tb for tb in tb_meta if tb.jira_issues]
    elif filter_text == 'No Ticket':
        tb_meta = [tb for tb in tb_meta if not tb.jira_issues]
    elif filter_text == 'Has Open Ticket':
        tb_meta = [
            tb for tb in tb_meta if
            [issue for issue in tb.jira_issues if issue.status != 'Closed']
        ]
    else:
        tb_meta = tb_meta

    # we take at most 100 tracebacks, due to performance issues of having more
    tb_meta = tb_meta[:100]

    # for each traceback, get all similar tracebacks
    with tracer.start_span('for each traceback, get similar tracebacks ', child_of=root_span) as span:
        with span_in_context(span):
            for tb in tb_meta:
                tb.similar_tracebacks = traceback_database.get_matching_tracebacks(
                    ES, tracer, tb.traceback.traceback_text, es_util.EXACT_MATCH, 100
                )

    return tb_meta


def render_main_page(ES, tracer, days_ago:int, filter_text:str):
    """
        Renders our index page with all the Trackbacks for the specified day and filter.
    """
    tracer = tracer or opentracing.tracer
    root_span = get_current_span()
    assert False

    # our papertrail logs are saved in Eastern Time
    today = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
    date_to_analyze = today - datetime.timedelta(days=days_ago)

    tb_meta = get_tracebacks_for_day(ES, tracer, date_to_analyze, filter_text)

    with tracer.start_span('render page', child_of=root_span) as span:
        with span_in_context(span):
            render = flask.render_template(
                'index.html',
                tb_meta=tb_meta,
                show_restore_button=__user_has_hidden_tracebacks(),
                date_to_analyze=date_to_analyze,
                days_ago=days_ago,
                filter_text=filter_text
            )
    return render


def __user_has_hidden_tracebacks():
    """
        Returns True if the user has hidden any tracebacks using /hide_traceback this session
    """
    return flask.session.get(text_keys.HIDDEN_TRACEBACK) is not None


def parse_s3_for_date(date_, bucket, key_prefix):
    """
        Queues jobs to parse s3 for the given date
    """
    for hour in range(0, 24):
        filename_string = 'dt=%s/%s-%02d.tsv.gz' % (date_, date_, hour)
        key = '/'.join((key_prefix, filename_string))
        logger.info("adding to s3 parse queue. bucket: '%s', key: '%s'", bucket, key)
        tasks.parse_log_file.delay(bucket, key)
