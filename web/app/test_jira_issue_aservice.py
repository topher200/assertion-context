# import unittest
# import vcr_unittest

# from web.app import jira_issue_aservice


# class TestJiraIssueAService(vcr_unittest.VCRTestCase):
#     def _get_vcr_kwargs(self, **kwargs):
#         kwargs['decode_compressed_response'] = True
#         return kwargs

#     def test_jira_api_object_to_JiraIssue(self):
#         i = jira_issue_aservice.get_issue('PPC-12345')
#         assert False, (dir(i), vars(i))

#         # jira_object = jira.resources.Issue


import unittest

from web.app import jira_issue_aservice


class TestJiraIssueAService(unittest.TestCase):
    def test_jira_api_object_to_JiraIssue(self):
        i = jira_issue_aservice.get_issue('PPC-12345')
        assert False, (dir(i), vars(i))

        # jira_object = jira.resources.Issue
