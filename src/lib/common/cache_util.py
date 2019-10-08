from typing import Optional
import logging

from lib.jira import (
    jira_issue_db,
)
from lib.traceback import (
    traceback_db,
)
import tasks


logger = logging.getLogger()


def invalidate_cache(cache:Optional[str]):
    """
        Invalidate all (or a subset of) the dogpile function caches
    """
    if cache is None or cache == 'traceback':
        logger.info('invalidating traceback cache')
        traceback_db.invalidate_cache()
    if cache is None or cache == 'jira':
        logger.info('invalidating jira cache')
        jira_issue_db.invalidate_cache()
    tasks.hydrate_cache.apply_async(tuple(), expires=60) # expire after a minute
    return 'success'
