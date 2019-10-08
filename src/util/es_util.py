EXACT_MATCH = 100 # percent
SIMILAR_MATCH = 98 # percent
ALL_MATCH_LEVELS = set((
    EXACT_MATCH,
    SIMILAR_MATCH
))

def generate_text_match_payload(text, fields_to_match_against, match_level):
    """
        Given a text to match against and a list of fields_to_match_against, creates an ES query
        payload that finds match_level matches.

        We remove the final word of the query text. This allows us to ignore strings (like profile
        names or email addresses) that are unique on each hit. As a side effect we also strip
        newlines.

        How close the match will be is goverend by match_level. It must be in ALL_MATCH_LEVELS

        @return: a payload dict that can be sent directly to ES
    """
    assert isinstance(fields_to_match_against, list), (
        type(fields_to_match_against), fields_to_match_against
    )
    assert match_level in ALL_MATCH_LEVELS, (match_level, ALL_MATCH_LEVELS)

    if match_level is SIMILAR_MATCH:
        culled_text = ' '.join(text.split()[:-1])  # remove final word
    else:
        culled_text = text

    return {
        "query": {
            "multi_match": {
                "query": culled_text,
                "fields": fields_to_match_against,
                "type": "phrase",
            }
        }
    }
