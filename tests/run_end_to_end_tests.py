import os
import subprocess
import tempfile
import time

import pytest
import requests

from common_util import config_util


BADCORP_PAPERTRAIL_API_KEY = config_util.get('BADCORP_PAPERTRAIL_API_KEY')
assert BADCORP_PAPERTRAIL_API_KEY

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKEFILE_PATH = os.path.join(ROOT_DIR, 'Makefile')
PAPERTRAIL_API_CONFIG = os.path.join(ROOT_DIR, '.papertrail.yml')


def test_papertrail_to_elasticsearch_integration(setup_server_daemon):
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
    result_string = str(res)
    assert 'KeyError' in result_string

    # run healthcheck to make sure server is up
    res = requests.get('http://localhost:8000/healthz')
    assert res.ok, res

    # # run the realtime updater from server.py
    # res = requests.post('http://localhost:8000/realtime_update')
    # assert res.ok, res


@pytest.fixture(scope='module')
def setup_server_daemon(request):
    # run server.py, locally
    res = subprocess.check_output('make run-server-daemon', cwd=ROOT_DIR, shell=True, universal_newlines=True)
    container_id = res.strip().splitlines()[-1]

    def check_server_is_running():
        docker_ps_output = str(subprocess.check_output('docker ps -a --no-trunc | grep {}'.format(container_id),
                                                       shell=True,
                                                       universal_newlines=True))
        server_logs = str(subprocess.check_output('docker logs {}'.format(container_id),
                                                  shell=True,
                                                  universal_newlines=True))
        assert 'Up' in docker_ps_output, server_logs

    check_server_is_running()
    # still running after sleeping for a second?
    time.sleep(1)
    check_server_is_running()

    def teardown_server_daemon():
        subprocess.call('docker kill {}'.format(container_id), shell=True, universal_newlines=True)
    request.addfinalizer(teardown_server_daemon)
