# AService functions for performing our most high-level API actions

import datetime
import logging
import typing

import flask
import opentracing
import pytz

from opentracing_instrumentation.request_context import get_current_span, span_in_context

from . import (
    es_util,
    jira_issue_aservice,
    jira_issue_db,
    tasks,
    text_keys,
    traceback_database,
)
from .business_logic import slack_channel

logger = logging.getLogger()

TWO_WEEKS_AGO = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)


class TracebackPlusMetadata():
    """
        A lightweight class to hold a Traceback plus some metadata.

        We made a class (instead of a namedtuple) so that we can build incrementally.
    """
    def __init__(self, traceback):
        self.traceback = traceback
        self.jira_issues = None
        self.similar_jira_issues = None
        self.similar_tracebacks = None

    __slots__ = [
        'traceback',
        'jira_issues',
        'similar_jira_issues',
        'similar_tracebacks',
    ]


def get_tracebacks_for_day(
        ES, tracer, date_to_analyze:datetime.date, filter_text:str, hidden_traceback_ids:set,
) -> typing.List[TracebackPlusMetadata]:
    """
        Retrieves the Tracebacks for the given date_to_analyze date.

        If provided, only returns Tracebacks which match filter_text.

        Only returns Tracebacks whose ids aren't in hidden_traceback_ids.
    """
    tracer = tracer or opentracing.tracer
    root_span = get_current_span()

    # get all tracebacks
    with tracer.start_span('get all tracebacks', child_of=root_span) as span:
        with span_in_context(span):
            tracebacks = traceback_database.get_tracebacks(ES, tracer, date_to_analyze, date_to_analyze)
    logger.debug('found %s tracebacks', len(tracebacks))

    # filter out tracebacks the user has hidden. we use a namedlist to store each traceback + some
    # metadata we'll use when rendering the html page
    tb_meta = [
        TracebackPlusMetadata(traceback=t) for t in tracebacks
        if t.origin_papertrail_id not in hidden_traceback_ids
    ]

    # get a list of matching jira issues
    with tracer.start_span('for each traceback, get matching jira issues', child_of=root_span) as span:
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
    elif filter_text == 'No Recent Ticket':
        tb_meta_without_recent_ticket = []
        for tb in tb_meta:
            has_recent_issues = False
            for issue in tb.jira_issues:
                if issue.updated > TWO_WEEKS_AGO:
                    has_recent_issues = True
                    break
            if not has_recent_issues:
                tb_meta_without_recent_ticket.append(tb)
        tb_meta = tb_meta_without_recent_ticket
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
    with tracer.start_span('for each traceback, get similar tracebacks', child_of=root_span) as span:
        with span_in_context(span):
            for tb in tb_meta:
                tb.similar_tracebacks = []
                tb.similar_tracebacks = traceback_database.get_matching_tracebacks(
                    ES, tracer, tb.traceback.traceback_text, es_util.EXACT_MATCH, 100
                )

    return tb_meta


def render_main_page(ES, tracer, days_ago:int, filter_text:str, hidden_traceback_ids:set):
    """
        Renders our index page with all the Trackbacks for the specified day and filter.
    """
    tracer = tracer or opentracing.tracer
    root_span = get_current_span()

    # our papertrail logs are saved in Eastern Time
    today = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
    date_to_analyze = today - datetime.timedelta(days=days_ago)

    tb_meta = get_tracebacks_for_day(ES, tracer, date_to_analyze, filter_text, hidden_traceback_ids)

    with tracer.start_span('render page', child_of=root_span) as span:
        with span_in_context(span):
            render = flask.render_template(
                'index.html',
                tb_meta=tb_meta,
                show_restore_button=len(hidden_traceback_ids) > 0,
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


def create_ticket(
        ES, origin_papertrail_id:int, assign_to:typing.Optional[str], reject_if_ticket_exists:bool
) -> str:
    """
        Creates a jira issue for the given traceback id
    """
    traceback = traceback_database.get_traceback(ES, origin_papertrail_id)

    if reject_if_ticket_exists:
        jira_issues = jira_issue_db.get_matching_jira_issues(
            ES, None, traceback.traceback_text, es_util.EXACT_MATCH
        )
        if jira_issues:
            key = jira_issues[0].key
            channel = slack_channel.get_channel_name(traceback)
            logger.info('Not creating Jira issue - already found %s', key)
            tasks.tell_slack_about_error(channel, "Issue has already been created as %s" % key)

    # find a list of tracebacks that use that text
    similar_tracebacks = traceback_database.get_matching_tracebacks(
        ES, opentracing.tracer, traceback.traceback_text, es_util.EXACT_MATCH, 50
    )

    # create a description using the list of tracebacks
    description = jira_issue_aservice.create_description(similar_tracebacks)

    # create a title using the traceback text
    title = jira_issue_aservice.create_title(traceback.traceback_text)

    if assign_to:
        assign_to_team = jira_issue_aservice.AssignToTeam(assign_to)
    else:
        assign_to_team = jira_issue_aservice.AssignToTeam('UNASSIGNED')

    # make API call to jira
    ticket_id = jira_issue_aservice.create_jira_issue(title, description, assign_to_team)

    # tell slack that we made a new ticket (async)
    channel = slack_channel.get_channel_name(traceback)
    tasks.tell_slack_about_new_jira_ticket.delay(channel, ticket_id)

    return ticket_id

def create_comment_on_existing_ticket(
        ES, existing_jira_issue_key:str, origin_papertrail_id:int
):
    """
        Given an existing Jira ticket id, create a comment on that ticket describing a NEW (but
        related) traceback that we've encountered, referenced by L{origin_papertrail_id}.
    """
    traceback = traceback_database.get_traceback(ES, origin_papertrail_id)

    # find a list of tracebacks that use that text
    similar_tracebacks = traceback_database.get_matching_tracebacks(
        ES, opentracing.tracer, traceback.traceback_text, es_util.EXACT_MATCH, 50
    )

    # get the list of jira issues that this traceback matches. if our given issue key comes back in
    # the set of matching jira issues, it means that the full traceback.text is already on our
    # ticket and we don't need to post it again
    existing_issue = None
    for issue in jira_issue_db.get_matching_jira_issues(
        ES, opentracing.tracer, traceback.traceback_text, es_util.EXACT_MATCH
    ):
        if issue.key == existing_jira_issue_key:
            existing_issue = issue
            break

    # create a comment description using the list of tracebacks
    comment = ''
    if existing_issue:
        # we need only need to post the new hits. filter out any tracebacks that are after the
        # latest one already on that ticket
        latest = jira_issue_aservice.find_latest_referenced_id(existing_issue)
        if latest is not None:
            tracebacks_to_comment = [
                tb for tb in similar_tracebacks
                if int(tb.origin_papertrail_id) > latest
            ]
        else:
            # just take the them all
            tracebacks_to_comment = similar_tracebacks
        logger.info('found latest papertrail id %s. taking %s tracebacks of %s total found',
                    latest, len(tracebacks_to_comment), len(similar_tracebacks))
        comment = jira_issue_aservice.create_comment_with_hits_list(tracebacks_to_comment)
    else:
        # we need a full comment with the traceback description and all hits
        comment = jira_issue_aservice.create_description(similar_tracebacks)

    # leave the comment
    jira_issue = jira_issue_aservice.get_issue(existing_jira_issue_key)
    assert jira_issue
    jira_issue_aservice.create_comment(jira_issue, comment)

    # tell slack that we updated the ticket (async)
    channel = slack_channel.get_channel_name(traceback)
    tasks.tell_slack_about_updated_jira_ticket.delay(channel, jira_issue.key)
