import sys
import os
import json

# Add the project root to the Python path to allow importing gemini_intruder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gemini_intruder import (
    IntruderRequest,
    HTTPRequestData,
    Resource,
    ResourceType,
    RequestPart,
    AuthzTester,
    HTTPClient,
    RequestResources,
)

# Setup common test fixtures
def create_tester():
    """Create a fresh AuthzTester instance for testing."""
    dummy_client = HTTPClient()
    return AuthzTester(http_client=dummy_client)

def create_resource_types():
    """Create common resource types used in tests."""
    return {
        "product": ResourceType(name="Product", description="Store product"),
        "order": ResourceType(name="Order", description="Customer order")
    }

def test_modify_url_parameter():
    """Tests replacement of a resource ID in the URL."""
    tester = create_tester()
    resource_types = create_resource_types()
    
    original_id = "25"
    target_id = "99"
    resource_type_name = resource_types["product"].name
    url = f"http://example.com/products/{original_id}/details/"

    # Resource info indicating ID is in the URL
    res_info = Resource(
        id=original_id,
        type=resource_types["product"],
        request_part=RequestPart.URL,
        selected_slice={RequestPart.URL: f"/products/{{id}}/"}
    )
    auth_info = RequestResources(resources=[res_info], description="Get product")

    base_data = HTTPRequestData(
        method="GET",
        url=url,
        headers={"Accept": "application/json"},
        post_data=None,
    )
    base_request = IntruderRequest(data=base_data, user_id="user1", auth_info=auth_info)

    modified_request = tester.modify_request_for_resource(
        base_request, target_id, resource_type_name
    )

    assert modified_request is not None, "Modified request should not be None"
    expected_url = f"http://example.com/products/{target_id}/details/"
    assert modified_request.url == expected_url, "URL should be modified"
    assert modified_request.method == base_request.method, "Method should be unchanged"
    assert modified_request.post_data == base_request.post_data, "POST data should be unchanged"
    assert modified_request.headers["Accept"] == base_request.headers["Accept"], "Headers should be largely unchanged"

def test_modify_body_parameter_simple():
    """Tests replacement of a resource ID in a simple key-value POST body."""
    tester = create_tester()
    resource_types = create_resource_types()
    
    original_id = "10"
    target_id = "55"
    resource_type_name = resource_types["order"].name
    url = "http://example.com/orders/update/"

    post_body = f"csrf_token=abc&order_id={original_id}&status=pending"

    res_info = Resource(
        id=original_id,
        type=resource_types["order"],
        request_part=RequestPart.BODY,
        selected_slice={RequestPart.BODY: "order_id"}
    )
    auth_info = RequestResources(resources=[res_info], description="Update order")

    base_data = HTTPRequestData(
        method="POST",
        url=url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        post_data=post_body,
    )
    base_request = IntruderRequest(data=base_data, user_id="user2", auth_info=auth_info)

    modified_request = tester.modify_request_for_resource(
        base_request, target_id, resource_type_name
    )

    assert modified_request is not None, "Modified request should not be None"
    expected_post_data = f"csrf_token=abc&order_id={target_id}&status=pending"
    assert modified_request.post_data == expected_post_data, "POST data should be modified"
    assert modified_request.url == url, "URL should be unchanged"
    assert modified_request.method == base_request.method, "Method should be unchanged"

def test_modify_body_parameter_json():
    """Tests replacement of a resource ID within a JSON POST body."""
    tester = create_tester()
    resource_types = create_resource_types()
    
    original_id = "prod_abc"
    target_id = "prod_xyz"
    resource_type_name = resource_types["product"].name
    url = "http://example.com/cart/add/"

    post_body = json.dumps({"product_identifier": original_id, "quantity": 2})

    res_info = Resource(
        id=original_id,
        type=resource_types["product"],
        request_part=RequestPart.BODY,
        selected_slice={RequestPart.BODY: "product_identifier"}
    )
    auth_info = RequestResources(resources=[res_info], description="Add product to cart")

    base_data = HTTPRequestData(
        method="POST",
        url=url,
        headers={"Content-Type": "application/json"},
        post_data=post_body,
    )
    base_request = IntruderRequest(data=base_data, user_id="user3", auth_info=auth_info)

    modified_request = tester.modify_request_for_resource(
        base_request, target_id, resource_type_name
    )

    assert modified_request is not None, "Modified request should not be None"
    expected_post_data = json.dumps({"product_identifier": target_id, "quantity": 2})
    assert json.loads(modified_request.post_data) == json.loads(expected_post_data), "POST data (JSON) should be modified"
    assert modified_request.url == url, "URL should be unchanged"
    assert modified_request.method == base_request.method, "Method should be unchanged"

def test_modify_id_not_found_in_url():
    """Tests behavior when the original ID is not found in the URL."""
    tester = create_tester()
    resource_types = create_resource_types()
    
    original_id = "nonexistent"
    target_id = "99"
    resource_type_name = resource_types["product"].name
    url = "http://example.com/products/25/details/"  # URL does not contain original_id

    res_info = Resource(id=original_id, type=resource_types["product"], request_part=RequestPart.URL)
    auth_info = RequestResources(resources=[res_info], description="Get product")
    base_data = HTTPRequestData(method="GET", url=url, headers={}, post_data=None)
    base_request = IntruderRequest(data=base_data, user_id="user1", auth_info=auth_info)

    modified_request = tester.modify_request_for_resource(
        base_request, target_id, resource_type_name
    )

    assert modified_request is not None
    assert modified_request.url == url, "URL should be unchanged when ID not found"

def test_modify_id_not_found_in_body():
    """Tests behavior when the original ID is not found in the POST body."""
    tester = create_tester()
    resource_types = create_resource_types()
    
    original_id = "nonexistent"
    target_id = "55"
    resource_type_name = resource_types["order"].name
    url = "http://example.com/orders/update/"
    post_body = "csrf_token=abc&order_id=10&status=pending"  # Body does not contain original_id

    res_info = Resource(id=original_id, type=resource_types["order"], request_part=RequestPart.BODY)
    auth_info = RequestResources(resources=[res_info], description="Update order")
    base_data = HTTPRequestData(method="POST", url=url, headers={}, post_data=post_body)
    base_request = IntruderRequest(data=base_data, user_id="user2", auth_info=auth_info)

    modified_request = tester.modify_request_for_resource(
        base_request, target_id, resource_type_name
    )

    assert modified_request is not None
    assert modified_request.post_data == post_body, "POST data should be unchanged when ID not found"

def test_modify_no_resource_info_match():
    """Tests behavior when the resource type name doesn't match any resource in auth_info."""
    tester = create_tester()
    resource_types = create_resource_types()
    
    target_id = "99"
    resource_type_name = "NonExistentType"  # This type is not in auth_info
    url = "http://example.com/products/25/details/"

    res_info_product = Resource(id="25", type=resource_types["product"], request_part=RequestPart.URL)
    auth_info = RequestResources(resources=[res_info_product], description="Get product")

    base_data = HTTPRequestData(method="GET", url=url, headers={}, post_data=None)
    base_request = IntruderRequest(data=base_data, user_id="user1", auth_info=auth_info)

    modified_request = tester.modify_request_for_resource(
        base_request, target_id, resource_type_name
    )

    assert modified_request is None, "Should return None when resource type name doesn't match auth_info"