import os
import subprocess
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAKEFILE_PATH = os.path.join(ROOT_DIR, 'Makefile')
PAPERTRAIL_API_CONFIG = os.path.join(ROOT_DIR, '.papertrail.yml')


class TestBadCorpToPapertrail(unittest.TestCase):
    def test_badcorp_logs_get_saved_to_papertrail(self):
        subprocess.check_call('make run-badcorp', cwd=ROOT_DIR, shell=True)
        res = subprocess.check_output('papertrail -c {}'.format(PAPERTRAIL_API_CONFIG),
                                      shell=True,
                                      universal_newlines=True)
        self.assertIn('KeyError', res)
