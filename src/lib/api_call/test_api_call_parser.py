import collections
import datetime
import unittest

from web.app.entities.api_call import ApiCall
from web.app.services.api_call_parser import ApiCallParser


MATCHING_LOG_LINES = frozenset((
    '''742430301292376083	2016-12-05T14:00:00	2016-12-05T14:00:00Z	563850000	i-00000000000	54.85.100.30	User	Notice	aws1.engine.server.debug	05/Dec/2016:09:00:00.004 6012/WS#name-profile_name@name.com   : DEBUG    wordstream.services: f,1480946399.9936 IsGetInProgressHandler (GET) took 11 milliseconds to complete and final memory 236MB (delta -1MB)''',
    '''742430301430792226	2016-12-05T14:00:00	2016-12-05T14:00:00Z	563850000	i-00000000000	54.162.100.175	User	Notice	manager.debug	05/Dec/2016:09:00:00.038 25552/PV#name-profile_name@name.com   : DEBUG    wordstream.services: f,1480946399.9712 IsGetInProgressHandler (GET) took 67 milliseconds to complete and final memory 236MB (delta -1MB)''',
    '''742430307403477003	2016-12-05T14:00:01	2016-12-05T14:00:01Z	563850000	i-00000000000	54.85.100.30	User	Notice	aws1.engine.server.debug	05/Dec/2016:09:00:01.459 5754/WS#profile_name-adwords@email.com: DEBUG    wordstream.services: f,1480946401.4130 AddNegativesAlertHandler (POST) took 46 milliseconds to complete and final memory 236MB (delta -1MB)''',
    '''742430307768381446	2016-12-05T14:00:01	2016-12-05T14:00:01Z	563850000	i-00000000000	54.85.100.30	User	Notice	aws1.engine.server.debug	05/Dec/2016:09:00:01.548 5945/WS#profile_name-adwords@email.com: DEBUG    wordstream.services: f,1480946401.4818 BingAccountsHandler (GET) took 66 milliseconds to complete and final memory 236MB (delta 100MB)''',
    '''742430324398809120	2016-12-05T14:00:05	2016-12-05T14:00:05Z	563860000	i-00000000000	54.234.100.165	User	Notice	aws3.engine.server.debug	05/Dec/2016:09:00:05.516 17560/UV#name@email.com    : DEBUG    wordstream.services: f,1480946405.3795 BillingAccountIdHandler (GET) took 137 milliseconds to complete and final memory 236MB (delta -1MB)''',
    '''742430324398809120	2016-12-05T14:00:05	2016-12-05T14:00:05Z	563860000	i-00000000000	54.234.100.165	User	Notice	aws3.engine.server.debug	05/Dec/2016:09:00:05.516 17560/UV#name@email.com    : DEBUG    wordstream.services: f,1480946405.3795 BillingAccountIdHandler (GET) took 137 milliseconds to complete''',
))

NON_MATCHING_LOG_LINES = frozenset((
    '''742430301292376128	2016-12-05T14:00:00	2016-12-05T14:00:00Z	563850000	i-00000000000	54.85.100.30	User	Notice	aws1.engine.server.cherrypy.access	54.162.133.175 - - [05/Dec/2016:09:00:00] "GET /services/v1/adwords/is_get_in_progress HTTP/1.1" 200 28 "" "python-requests/2.11.1"''',
    '''742430301313347589	2016-12-05T14:00:00	2016-12-05T14:00:00Z	563870000	i-00000000000	54.165.100.114	User	Notice	update.debug	05/Dec/2016:09:00:00.008 8795/#upd:profile_name:28dc                   : WARNING  wordstream.update: No active goals! Returning...''',
    '''742430301317541890	2016-12-05T14:00:00	2016-12-05T14:00:00Z	563870000	i-00000000000	54.165.100.114	User	Notice	update.debug	05/Dec/2016:09:00:00.009 8795/#upd:profile_name:28dc                   : INFO     wordstream.update.TransitionAccountTargetCPAGoalCommand: Finished updating profile profile_name! (531 of 4729)''',
    '''742430301317541898	2016-12-05T14:00:00	2016-12-05T14:00:00Z	563870000	i-00000000000	54.165.100.114	User	Notice	update.debug	05/Dec/2016:09:00:00.009 8795/#upd:profile_name:28dc                   : DEBUG    wordstream.update.TransitionAccountTargetCPAGoalCommand: Command completed in 0s''',
    '''742430304744288285	2016-12-05T14:00:00	2016-12-05T14:00:00Z	563870000	i-00000000000	52.91.100.21	User	Notice	tag_manager.debug	05/Dec/2016:09:00:00.828 24037/MainThread                              : DEBUG    wordstream.services: f,1480946400.8282 RoutesMapHandler (GET) took 0 milliseconds to complete and final memory 236MB (delta -1MB)''',
))

# a raw api call and what we expect our generated ApiCall to look like
DUMMY_API_CALL = '''742430301292376083	2016-12-05T14:00:00	2016-12-05T14:00:00Z	563850000	i-00000000000	54.85.100.30	User	Notice	aws1.engine.server.debug	05/Dec/2016:09:00:00.004 6012/WS#name-profile_name@name.com   : DEBUG    wordstream.services: f,1480946399.9936 IsGetInProgressHandler (GET) took 11 milliseconds to complete and final memory 236MB (delta 100MB)'''
EXPECTED_ENTTIY_FROM_DUMMY_API_CALL = ApiCall(
    datetime.datetime.strptime('2016-12-05T09:00:00-0500', '%Y-%m-%dT%H:%M:%S%z'),
    '742430301292376083',
    'i-00000000000',
    'aws1.engine.server.debug',
    'IsGetInProgressHandler',
    'name',
    'profile_name@name.com',
    'GET',
    11,
    236,
    100,
)


class TestApiCallParser(unittest.TestCase):
    def test_that_we_get_expected_api_calls(self):
        """
            Test that when we give the parser lines that should match, they match
        """
        api_calls = ApiCallParser.parse_stream(MATCHING_LOG_LINES)
        self.assertIsInstance(api_calls, collections.Iterable)
        api_calls = list(api_calls)  # unpack generator
        self.assertEqual(len(api_calls), len(MATCHING_LOG_LINES))
        for entity in api_calls:
            self.assertIsInstance(entity, ApiCall)

    def test_that_we_do_not_see_unexpected_api_calls(self):
        """
            Test that when we give the parser lines that don't match, they don't match
        """
        api_calls = ApiCallParser.parse_stream(NON_MATCHING_LOG_LINES)
        self.assertIsInstance(api_calls, collections.Iterable)
        api_calls = list(api_calls)  # unpack generator
        self.assertEqual(len(api_calls), 0)

    def test_dummy_api_call(self):
        """
            Test that our dummy API call generates the expected ApiCall entity
        """
        api_calls = ApiCallParser.parse_stream((DUMMY_API_CALL,))
        self.assertIsInstance(api_calls, collections.Iterable)
        api_calls = list(api_calls)  # unpack generator
        self.assertEqual(len(api_calls), 1)
        self.maxDiff = None
        self.assertDictEqual(api_calls[0].document(), EXPECTED_ENTTIY_FROM_DUMMY_API_CALL.document())
