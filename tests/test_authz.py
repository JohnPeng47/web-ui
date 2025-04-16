import pytest
from unittest.mock import Mock

# Assuming the classes are importable from the correct path
# Adjust the import path based on your project structure
from gemini_intruder import (
    AuthzTester,
    HTTPClient,
    IntruderRequest,
    HTTPRequestData,
    AuthSession,
    RequestAuthInfo,
    Resource,
    ResourceType,
    RequestPart,
)

class TestAuthzTester:
    def test_ingest_triggers_correct_tests(self):
        """Test that ingest correctly triggers tests based on new users, actions, and resources."""
        
        # 1. Setup Mock HTTPClient and AuthzTester
        mock_client = Mock(spec=HTTPClient)
        mock_client.send.return_value = None  # Don't actually send requests
        tester = AuthzTester(http_client=mock_client)
        
        # 2. Setup mock sessions and resource types
        user_a_session = Mock(spec=AuthSession)
        user_b_session = Mock(spec=AuthSession)
        user_c_session = Mock(spec=AuthSession)
        type1 = ResourceType(name="Type1", description="Test Type 1")
        type2 = ResourceType(name="Type2", description="Test Type 2")
        
        # 3. Test Cases - create and ingest request sequences using compact initialization
        
        # --- Request 1: User A accesses Resource R1 (Type1) via Action 1 ---
        req1 = IntruderRequest(
            data=HTTPRequestData(
                method="GET", 
                url="/type1/resource/R1", 
                headers={"cookie": "a_session=1"},
                post_data=None,
                is_iframe=False,
                redirected_from_url=None,
                redirected_to_url=None
            ),
            user_id="UserA",
            auth_info=RequestAuthInfo(
                resources=[
                    Resource(
                        id="R1", 
                        type=type1, 
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type1/resource/{id}"}
                    )
                ], 
                description="Access R1"
            )
        )
        req1._auth_session = user_a_session  # Still need to manually attach session
        
        tester.ingest(req1)
        assert tester.performed_tests == set(), "No tests should be triggered after first request"
        
        # --- Request 2: User B accesses Resource R2 (Type2) via Action 2 ---
        req2 = IntruderRequest(
            data=HTTPRequestData(
                method="GET", 
                url="/type2/resource/R2", 
                headers={"cookie": "b_session=1"},
                post_data=None,
                is_iframe=False,
                redirected_from_url=None,
                redirected_to_url=None
            ),
            user_id="UserB",
            auth_info=RequestAuthInfo(
                resources=[
                    Resource(
                        id="R2", 
                        type=type2, 
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type2/resource/{id}"}
                    )
                ], 
                description="Access R2"
            )
        )
        req2._auth_session = user_b_session
        
        tester.ingest(req2)
        assert tester.performed_tests == set(), "No cross-type tests expected after second request"
        
        # --- Request 3: User A accesses Resource R1a (Type1) via Action 1 ---
        req3 = IntruderRequest(
            data=HTTPRequestData(
                method="GET", 
                url="/type1/resource/R1",  # Same URL as req1
                headers={"cookie": "a_session=1"},
                post_data=None,
                is_iframe=False,
                redirected_from_url=None,
                redirected_to_url=None
            ),
            user_id="UserA",
            auth_info=RequestAuthInfo(
                resources=[
                    Resource(
                        id="R1a",  # New resource ID of existing type
                        type=type1, 
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type1/resource/{id}"}
                    )
                ], 
                description="Access R1a"
            )
        )
        req3._auth_session = user_a_session
        
        tester.ingest(req3)
        expected_after_req3 = {
            ("UserB", "R1a", "/type1/resource/R1")  # Test case 2: UserB tries Action 1 on new resource R1a
        }
        assert tester.performed_tests == expected_after_req3, "Expected UserB to test access to R1a after request 3"
        
        # --- Request 4: User B accesses Resource R1 (Type1) via Action 3 ---
        req4 = IntruderRequest(
            data=HTTPRequestData(
                method="GET", 
                url="/type1/action3",  # New URL/action
                headers={"cookie": "b_session=1"},
                post_data=None,
                is_iframe=False,
                redirected_from_url=None,
                redirected_to_url=None
            ),
            user_id="UserB",
            auth_info=RequestAuthInfo(
                resources=[
                    Resource(
                        id="R1",  # Existing resource 
                        type=type1, 
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type1/action3/{id}"}
                    )
                ], 
                description="Action3 on R1"
            )
        )
        req4._auth_session = user_b_session
        
        tester.ingest(req4)
        expected_after_req4 = {
            ("UserB", "R1a", "/type1/resource/R1"),  # From previous request
            ("UserA", "R1", "/type1/action3")        # Test case 1: UserA tries new Action 3 on R1
        }
        assert tester.performed_tests == expected_after_req4, "Expected UserA to test new action after request 4"
        
        # --- Request 5: User C accesses Resource R1 (Type1) via Action 1 ---
        req5 = IntruderRequest(
            data=HTTPRequestData(
                method="GET", 
                url="/type1/resource/R1",  # Same as first action
                headers={"cookie": "c_session=1"},
                post_data=None,
                is_iframe=False,
                redirected_from_url=None,
                redirected_to_url=None
            ),
            user_id="UserC",
            auth_info=RequestAuthInfo(
                resources=[
                    Resource(
                        id="R1", 
                        type=type1, 
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type1/resource/{id}"}
                    )
                ], 
                description="UserC access R1"
            )
        )
        req5._auth_session = user_c_session
        
        tester.ingest(req5)
        
        final_expected_tests = {
            # From previous requests
            ("UserB", "R1a", "/type1/resource/R1"),  # UserB tests R1a
            ("UserA", "R1", "/type1/action3"),       # UserA tests Action3
            
            # New from request 5 - test case 3 (new user)
            ("UserC", "R2", "/type2/resource/R2"),   # UserC tries Action 2 on R2
            ("UserC", "R1", "/type1/action3"),       # UserC tries Action 3 on R1
            
            # New from request 5 - test case 2 (existing resource type)
            ("UserB", "R1", "/type1/action3"),       # UserB tries Action 3 on R1
        }
        
        assert tester.performed_tests == final_expected_tests, "Failed final state verification for all test cases"
        
        # Verify send() was called the correct number of times
        expected_call_count = len(final_expected_tests)
        assert mock_client.send.call_count == expected_call_count, f"Expected {expected_call_count} calls to send()"
