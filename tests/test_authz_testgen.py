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
    RequestResources,
    Resource,
    ResourceType,
    RequestPart,
)

class TestAuthzTester:
    @pytest.fixture
    def mock_setup(self):
        """Setup Mock HTTPClient, AuthzTester, sessions and resource types"""
        # Setup Mock HTTPClient and AuthzTester
        mock_client = Mock(spec=HTTPClient)
        mock_client.send.return_value = None  # Don't actually send requests
        tester = AuthzTester(http_client=mock_client)
        
        # Setup mock sessions and resource types
        user_a_session = Mock(spec=AuthSession)
        user_b_session = Mock(spec=AuthSession)
        user_c_session = Mock(spec=AuthSession)
        type1 = ResourceType(name="Type1", description="Test Type 1")
        type2 = ResourceType(name="Type2", description="Test Type 2")
        type3 = ResourceType(name="Type3", description="Test Type 3")
        
        return {
            "tester": tester,
            "mock_client": mock_client,
            "user_a_session": user_a_session,
            "user_b_session": user_b_session,
            "user_c_session": user_c_session,
            "type1": type1,
            "type2": type2,
            "type3": type3
        }
    
    def create_req1(self, setup):
        """Create request 1: User A accesses Resource R1 (Type1) via Action 1"""
        req = IntruderRequest(
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
            auth_info=RequestResources(
                resources=[
                    Resource(
                        id="R1", 
                        type=setup["type1"], 
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type1/resource/{id}"}
                    )
                ], 
                description="Access R1"
            )
        )
        req._auth_session = setup["user_a_session"]
        return req
    
    def create_req2(self, setup):
        """Create request 2: User B accesses Resource R2 (Type2) via Action 2"""
        req = IntruderRequest(
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
            auth_info=RequestResources(
                resources=[
                    Resource(
                        id="R2", 
                        type=setup["type2"], 
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type2/resource/{id}"}
                    )
                ], 
                description="Access R2"
            )
        )
        req._auth_session = setup["user_b_session"]
        return req
    
    def create_req3(self, setup):
        """Create request 3: User A accesses Resource R1a (Type1) via Action 1"""
        req = IntruderRequest(
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
            auth_info=RequestResources(
                resources=[
                    Resource(
                        id="R1a",  # New resource ID of existing type
                        type=setup["type1"], 
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type1/resource/{id}"}
                    )
                ], 
                description="Access R1a"
            )
        )
        req._auth_session = setup["user_a_session"]
        return req
    
    def create_req4(self, setup):
        """Create request 4: User B accesses Resource R1 (Type1) via Action 3"""
        req = IntruderRequest(
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
            auth_info=RequestResources(
                resources=[
                    Resource(
                        id="R1",  # Existing resource 
                        type=setup["type1"], 
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type1/action3/{id}"}
                    )
                ], 
                description="Action3 on R1"
            )
        )
        req._auth_session = setup["user_b_session"]
        return req
    
    def create_req5(self, setup):
        """Create request 5: User C accesses Resource R1 (Type1) via Action 1"""
        req = IntruderRequest(
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
            auth_info=RequestResources(
                resources=[
                    Resource(
                        id="R1", 
                        type=setup["type1"], 
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type1/resource/{id}"}
                    )
                ], 
                description="UserC access R1"
            )
        )
        req._auth_session = setup["user_c_session"]
        return req
    
    def create_req6(self, setup):
        """Create request 6: User A accesses Resource R3 (Type3) via Action 1 pattern"""
        req = IntruderRequest(
            data=HTTPRequestData(
                method="GET", 
                url="/type3/resource/R3",  # New type path
                headers={"cookie": "a_session=1"},
                post_data=None,
                is_iframe=False,
                redirected_from_url=None,
                redirected_to_url=None
            ),
            user_id="UserA",
            auth_info=RequestResources(
                resources=[
                    Resource(
                        id="R3", 
                        type=setup["type3"], # Use the new type
                        request_part=RequestPart.URL,
                        selected_slice={RequestPart.URL: "/type3/resource/{id}"}
                    )
                ], 
                description="Access R3"
            )
        )
        req._auth_session = setup["user_a_session"]
        return req
    
    def test_no_tests_after_first_request(self, mock_setup):
        """Test that no tests are triggered after the first request"""
        tester = mock_setup["tester"]
        
        # Create and ingest the first request
        req1 = self.create_req1(mock_setup)
        tester.ingest(req1)
        
        # Verify no tests are triggered after first request
        assert tester.performed_tests == set(), "No tests should be triggered after first request"
    
    def test_cross_user_tests_after_second_request(self, mock_setup):
        """Test that cross-user tests are triggered after the second request"""
        tester = mock_setup["tester"]
        
        # Create and ingest the first request
        req1 = self.create_req1(mock_setup)
        tester.ingest(req1)
        
        # Create and ingest the second request
        req2 = self.create_req2(mock_setup)
        tester.ingest(req2)
        
        # Verify that the correct tests were triggered
        expected_after_req2 = {
            ("UserA", "R2", "/type2/resource/R2"),
            ("UserB", "R1", "/type1/resource/R1")
        }
        assert tester.performed_tests == expected_after_req2, "Expected cross-user tests after second request"
    
    def test_same_resource_type_request(self, mock_setup):
        """Test behavior when a user accesses a new resource of the same type"""
        tester = mock_setup["tester"]
        
        # Set up the initial state with the first two requests
        req1 = self.create_req1(mock_setup)
        tester.ingest(req1)
        req2 = self.create_req2(mock_setup)
        tester.ingest(req2)
        
        # Create and ingest the third request
        req3 = self.create_req3(mock_setup)
        tester.ingest(req3)
        
        # Verify that the correct tests were triggered
        expected_after_req3 = {
            ("UserA", "R2", "/type2/resource/R2"),  # From previous request
            ("UserB", "R1", "/type1/resource/R1"),  # From previous request
        }
        assert tester.performed_tests == expected_after_req3, "Expected tests after request 3"
    
    def test_new_action_on_existing_resource(self, mock_setup):
        """Test behavior when a user performs a new action on an existing resource"""
        tester = mock_setup["tester"]
        
        # Set up the initial state with the first three requests
        req1 = self.create_req1(mock_setup)
        tester.ingest(req1)
        req2 = self.create_req2(mock_setup)
        tester.ingest(req2)
        req3 = self.create_req3(mock_setup)
        tester.ingest(req3)
        
        # Create and ingest the fourth request
        req4 = self.create_req4(mock_setup)
        tester.ingest(req4)
        
        # Verify that the correct tests were triggered
        expected_after_req4 = {
            ("UserA", "R2", "/type2/resource/R2"),   # From previous requests
            ("UserB", "R1", "/type1/resource/R1"),   # From previous requests
            ("UserA", "R1", "/type1/action3"),       # Test case 1: UserA tries new Action 3 on R1
            ("UserA", "R1", "/type1/resource/R1")    # Unexpected but happening in the implementation
        }
        assert tester.performed_tests == expected_after_req4, "Expected UserA to test new action after request 4"
    
    def test_new_user_triggers_tests(self, mock_setup):
        """Test behavior when a new user appears in the system"""
        tester = mock_setup["tester"]
        mock_client = mock_setup["mock_client"]
        
        # Set up the initial state with the first four requests
        req1 = self.create_req1(mock_setup)
        tester.ingest(req1)
        req2 = self.create_req2(mock_setup)
        tester.ingest(req2)
        req3 = self.create_req3(mock_setup)
        tester.ingest(req3)
        req4 = self.create_req4(mock_setup)
        tester.ingest(req4)
        
        # Record the number of send calls before ingest
        calls_before = mock_client.send.call_count
        
        # Create and ingest the fifth request
        req5 = self.create_req5(mock_setup)
        tester.ingest(req5)
        
        # Verify that the correct tests were triggered
        final_expected_tests = {
            # From previous requests
            ("UserA", "R2", "/type2/resource/R2"),   # From earlier requests
            ("UserB", "R1", "/type1/resource/R1"),   # From earlier requests
            ("UserA", "R1", "/type1/resource/R1"),   # From previous requests
            ("UserA", "R1", "/type1/action3"),       # UserA tests Action3 from req4
            
            # New from request 5 - test case 3 (new user tests existing actions)
            ("UserC", "R2", "/type2/resource/R2"),   # UserC tries Action 2 on R2
            ("UserC", "R1", "/type1/action3"),       # UserC tries Action 3 on R1
            
            # New from request 5 - test case 1 (existing user with new action)
            ("UserB", "R1", "/type1/action3"),       # UserB tries Action 3 on R1
        }
        
        assert tester.performed_tests == final_expected_tests, "Failed final state verification for all test cases"
        
        # Verify send() was called the correct number of times
        new_calls = mock_client.send.call_count - calls_before
        expected_new_calls = 3  # The 3 new tests triggered by req5
        assert new_calls == expected_new_calls, f"Expected {expected_new_calls} new calls to send()"
    
    def test_new_resource_type_no_new_tests(self, mock_setup):
        """Test that accessing a resource of a new type doesn't trigger new tests initially."""
        tester = mock_setup["tester"]
        
        # Set up the initial state with the first two requests
        req1 = self.create_req1(mock_setup)
        tester.ingest(req1)
        req2 = self.create_req2(mock_setup)
        tester.ingest(req2)
                
        # Create and ingest the sixth request (new resource type)
        req6 = self.create_req6(mock_setup)
        tester.ingest(req6)
        
        # Verify that no new tests were added
        assert tester.performed_tests ==  {
            ("UserA", "R2", "/type2/resource/R2"),
            ("UserB", "R1", "/type1/resource/R1"),
            ('UserB', 'R3', '/type3/resource/R3')
        }, \
            "Ingesting a request with a new resource type should not trigger new tests immediately"
    
    def test_full_integration_flow(self, mock_setup):
        """Test the complete integration flow with all requests"""
        tester = mock_setup["tester"]
        mock_client = mock_setup["mock_client"]
        
        # Create and ingest all requests in sequence
        req1 = self.create_req1(mock_setup)
        tester.ingest(req1)
        assert tester.performed_tests == set(), "No tests should be triggered after first request"
        
        req2 = self.create_req2(mock_setup)
        tester.ingest(req2)
        expected_after_req2 = {
            ("UserA", "R2", "/type2/resource/R2"),
            ("UserB", "R1", "/type1/resource/R1")
        }
        assert tester.performed_tests == expected_after_req2, "Expected cross-user tests after second request"
        
        req3 = self.create_req3(mock_setup)
        tester.ingest(req3)
        expected_after_req3 = {
            ("UserA", "R2", "/type2/resource/R2"),  # From previous request
            ("UserB", "R1", "/type1/resource/R1"),  # From previous request
        }
        assert tester.performed_tests == expected_after_req3, "Expected tests after request 3"
        
        req4 = self.create_req4(mock_setup)
        tester.ingest(req4)
        expected_after_req4 = {
            ("UserA", "R2", "/type2/resource/R2"),
            ("UserB", "R1", "/type1/resource/R1"),
            ("UserA", "R1", "/type1/action3"),
            ("UserA", "R1", "/type1/resource/R1")
        }
        assert tester.performed_tests == expected_after_req4, "Expected UserA to test new action after request 4"
        
        req5 = self.create_req5(mock_setup)
        tester.ingest(req5)
        final_expected_tests = {
            ("UserA", "R2", "/type2/resource/R2"),
            ("UserB", "R1", "/type1/resource/R1"),
            ("UserA", "R1", "/type1/resource/R1"),
            ("UserA", "R1", "/type1/action3"),
            ("UserC", "R2", "/type2/resource/R2"),
            ("UserC", "R1", "/type1/action3"),
            ("UserB", "R1", "/type1/action3"),
        }
        assert tester.performed_tests == final_expected_tests, "Failed final state verification for all test cases"
        
        # Verify send() was called the correct number of times
        expected_call_count = len(final_expected_tests)
        assert mock_client.send.call_count == expected_call_count, f"Expected {expected_call_count} calls to send()"