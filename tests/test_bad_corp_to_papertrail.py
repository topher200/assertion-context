import os
import subprocess
import tempfile

from common.util import config


BADCORP_PAPERTRAIL_API_KEY = config.get('BADCORP_PAPERTRAIL_API_KEY')
assert BADCORP_PAPERTRAIL_API_KEY

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKEFILE_PATH = os.path.join(ROOT_DIR, 'Makefile')
PAPERTRAIL_API_CONFIG = os.path.join(ROOT_DIR, '.papertrail.yml')


def test_badcorp_logs_get_saved_to_papertrail():
    # run our Badcorp, saving tracebacks to papertrail
    # TODO: do we want to pass a uuid here and make sure we receive it on the other side? OR we
    # could use the box ID from the docker machine
    subprocess.check_call('make run-badcorp', cwd=ROOT_DIR, shell=True)

    # run the papertrail-cli and confirm that we see the Badcorp traceback
    with tempfile.NamedTemporaryFile(mode='w') as papertrail_creds_file:
        api_key_string = 'token: {}'.format(BADCORP_PAPERTRAIL_API_KEY)
        papertrail_creds_file.write(api_key_string)
        papertrail_creds_file.flush()
        res = subprocess.check_output('papertrail -c {}'.format(papertrail_creds_file.name),
                                      shell=True,
                                      universal_newlines=True)

    # check that we see the Traceback that was thrown
    result_string = str(res)
    assert 'KeyError' in result_string