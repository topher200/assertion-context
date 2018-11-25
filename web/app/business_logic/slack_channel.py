from ..traceback import Traceback


def get(traceback:Traceback):
    """
        Given a traceback, returns the name of the slack channel it belongs in.

        We look in the traceback's text for certain trigger words.
    """
    if 'facebook' in traceback.traceback_text.lower():
        return 'tracebacks-social'
    elif 'adwords' in traceback.traceback_text.lower():
        return 'tracebacks-adwords'
    else:
        return 'tracebacks'
