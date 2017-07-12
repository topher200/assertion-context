import logging


EXACT_MATCH = 100 # percent
SIMILAR_MATCH = 98 # percent
ALL_MATCH_LEVELS = set((
    EXACT_MATCH,
    SIMILAR_MATCH
))


logger = logging.getLogger()


def generate_text_match_payload(es, index, text, fields_to_match_against, match_level):
    """
        Given a text to match against and a list of fields_to_match_against, creates an ES query
        payload that finds matches.

        We run the provided text through our elasticsearch analysis filter to remove our traceback
        filtered keywords.

        How close the match will be is goverend by match_level. It must be in ALL_MATCH_LEVELS

        NOTE: Match level is currently unused.

        @return: a payload dict that can be sent directly to ES
    """
    assert isinstance(fields_to_match_against, list), (
        type(fields_to_match_against), fields_to_match_against
    )
    assert match_level in ALL_MATCH_LEVELS, (match_level, ALL_MATCH_LEVELS)

    # run input text through the ES filter to get a list of tokens
    raw_tokens = es.indices.analyze(index=index, analyzer='traceback_filtered', text=text)
    tokens = list(t['token'] for t in raw_tokens['tokens'])
    logger.warning('tokens: %s', tokens)
    logger.warning('query: %s', ' '.join((str(t) for t in tokens)))

    return {
        "query": {
            "multi_match": {
                "query": ' '.join((str(t) for t in tokens)),
                "fields": fields_to_match_against,
                "type": "phrase",
            }
        }
    }
