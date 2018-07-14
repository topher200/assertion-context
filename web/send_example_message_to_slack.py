import datetime
import random

from elasticsearch import Elasticsearch
import certifi
import pytz

from app import (
    api_aservice,
    config_util,
)
from app.services import (
    slack_poster,
)

# set up database
ES_ADDRESS = config_util.get('ES_ADDRESS')
ES = Elasticsearch([ES_ADDRESS], ca_certs=certifi.where())

# our papertrail logs are saved in Eastern Time
today = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
yesterday = today - datetime.timedelta(days=1)
print('getting tracebacks')
tracebacks_with_metadata = api_aservice.get_tracebacks_for_day(
    ES, None, today, 'No Ticket', set()
)
tb_meta = random.choice(tracebacks_with_metadata)
traceback = tb_meta.traceback
similar_tracebacks = tb_meta.similar_tracebacks

print('posting to slack')
response = slack_poster.post_traceback(traceback, similar_tracebacks)
print('posted. response: %s' % response)
print(response.text)
