EXACT_MATCH = 99 # percent
SIMILAR_MATCH = 98 # percent
ALL_MATCH_LEVELS = set((
    EXACT_MATCH,
    SIMILAR_MATCH
))

def generate_text_match_payload(text, field_to_match_against, match_level):
    """
        Given a text to match against and a field_to_match_against, creates an ES query payload
        that finds close/exact matches

        How close the match will be is goverend by match_level. It must be in ALL_MATCH_LEVELS

        @return: a payload dict that can be sent directly to ES
    """
    assert match_level in ALL_MATCH_LEVELS, (match_level, ALL_MATCH_LEVELS)

    return {
        "query": {
            "match": {
                field_to_match_against: {
                    "query": text,
                    "slop": 50,
                    "minimum_should_match": "%s%%" % match_level,
                    "cutoff_frequency": 0.001,
                }
            }
        }
    }
