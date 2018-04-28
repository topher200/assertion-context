# AService functions for performing our most high-level API actions

import datetime
import logging
import time
import types

import flask
import pytz

from app import (
    es_util,
    jira_issue_db,
    tasks,
    text_keys,
    traceback_database,
    tracing,
)

logger = logging.getLogger()
tracer = tracing.get_tracer()

DEBUG_TIMING = True # TODO: remove when we add opentracing


def render_main_page(ES, days_ago, filter_text):
    # our papertrail logs are saved in Eastern Time
    today = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
    date_to_analyze = today - datetime.timedelta(days=days_ago)

    # get all tracebacks
    with tracer.start_span('get_all_tracebacks') as span:
        span.log_kv({'event': 'get all tracebacks'})
        if DEBUG_TIMING:
            db_start_time = time.time()
        tracebacks = traceback_database.get_tracebacks(ES, date_to_analyze, date_to_analyze)
        if DEBUG_TIMING:
            flask.g.time_tracebacks = time.time() - db_start_time

    # create a set of tracebacks that match all the traceback texts the user has hidden
    if DEBUG_TIMING:
        hidden_tracebacks_start_time = time.time()
    hidden_tracebacks = set()
    if flask.session.get(text_keys.HIDDEN_TRACEBACK) is not None:
        for traceback_text in flask.session.get(text_keys.HIDDEN_TRACEBACK):
            for tb in traceback_database.get_matching_tracebacks(
                    ES, traceback_text, es_util.EXACT_MATCH, 10000
            ):
                hidden_tracebacks.add(tb.origin_papertrail_id)
        logger.info('found %s traceback ids we need to hide', len(hidden_tracebacks))
    if DEBUG_TIMING:
        flask.g.time_hidden_tracebacks = time.time() - hidden_tracebacks_start_time

    # filter out tracebacks the user has hidden. we use a SimpleNamespace to store each traceback +
    # some metadata we'll use when rendering the html page
    tb_meta = [
        types.SimpleNamespace(traceback=t) for t in tracebacks
        if t.origin_papertrail_id not in hidden_tracebacks
    ]

    # get a list of matching jira issues
    if DEBUG_TIMING:
        jira_issues_start_time = time.time()
    for tb in tb_meta:
        tb.jira_issues = jira_issue_db.get_matching_jira_issues(
            ES, tb.traceback.traceback_text, es_util.EXACT_MATCH
        )
        matching_jira_keys = set(jira_issue.key for jira_issue in tb.jira_issues)
        similar_jira_issues = jira_issue_db.get_matching_jira_issues(
            ES, tb.traceback.traceback_text, es_util.SIMILAR_MATCH
        )
        tb.similar_jira_issues = [similar_jira_issue for similar_jira_issue in similar_jira_issues
                                  if similar_jira_issue.key not in matching_jira_keys]
    if DEBUG_TIMING:
        flask.g.jira_issues_time = time.time() - jira_issues_start_time

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
    if DEBUG_TIMING:
        similar_tracebacks_start_time = time.time()
    for tb in tb_meta:
        tb.similar_tracebacks = traceback_database.get_matching_tracebacks(
            ES, tb.traceback.traceback_text, es_util.EXACT_MATCH, 100
        )
    if DEBUG_TIMING:
        flask.g.similar_tracebacks_time = time.time() - similar_tracebacks_start_time

    if DEBUG_TIMING:
        render_start_time = time.time()
    render = flask.render_template(
        'index.html',
        tb_meta=tb_meta,
        show_restore_button=__user_has_hidden_tracebacks(),
        date_to_analyze=date_to_analyze,
        days_ago=days_ago,
        filter_text=filter_text
    )
    if DEBUG_TIMING:
        flask.g.render_time = time.time() - render_start_time

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
