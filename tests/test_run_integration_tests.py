import os
import subprocess
import tempfile
import time

import pytest

from common.util import config


BADCORP_PAPERTRAIL_API_KEY = config.get('BADCORP_PAPERTRAIL_API_KEY')
assert BADCORP_PAPERTRAIL_API_KEY

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKEFILE_PATH = os.path.join(ROOT_DIR, 'Makefile')
PAPERTRAIL_API_CONFIG = os.path.join(ROOT_DIR, '.papertrail.yml')


def asdf_test_badcorp_logs_get_saved_to_papertrail():
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

def test_papertrail_to_elasticsearch_integration(setup_server_daemon):
    pass

@pytest.fixture(scope='module')
def setup_server_daemon(request):
    # run server.py, locally
    res = subprocess.check_output('make run-server-daemon', cwd=ROOT_DIR, shell=True, universal_newlines=True)
    container_id = res.strip().splitlines()[-1]

    docker_ps_output = str(subprocess.check_output('docker ps -a --no-trunc | grep {}'.format(container_id),
                                                   shell=True,
                                                   universal_newlines=True))
    server_logs = str(subprocess.check_output('docker logs {}'.format(container_id),
                                              shell=True,
                                              universal_newlines=True))
    assert 'Up' in docker_ps_output, server_logs

    time.sleep(1)
    docker_ps_output = str(subprocess.check_output('docker ps -a --no-trunc | grep {}'.format(container_id),
                                                   shell=True,
                                                   universal_newlines=True))
    server_logs = str(subprocess.check_output('docker logs {}'.format(container_id),
                                              shell=True,
                                              universal_newlines=True))
    assert 'Up' in docker_ps_output, server_logs

    def teardown_server_daemon():
        subprocess.call('docker kill {}'.format(container_id), shell=True, universal_newlines=True)
    request.addfinalizer(teardown_server_daemon)
