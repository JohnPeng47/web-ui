from src.agent.http_history import HTTPHandler
import pytest

@pytest.mark.asyncio
async def test_filter_scope(http_msgs):
    http_handler = HTTPHandler(
        scopes=[
            "http://147.79.78.153:3000/rest/",
            "http://147.79.78.153:3000/api/",
        ]
    )
    for r in http_msgs:
        req, res = r.request, r.response
        await http_handler.handle_request(req)
        await http_handler.handle_response(res, req)

    msgs = await http_handler.flush()    
    expected_urls = [
        "http://147.79.78.153:3000/rest/admin/application-version",
        "http://147.79.78.153:3000/rest/admin/application-configuration",
        "http://147.79.78.153:3000/rest/user/whoami",
        "http://147.79.78.153:3000/rest/languages",
        "http://147.79.78.153:3000/api/Challenges/?name=Score%20Board",
        "http://147.79.78.153:3000/rest/basket/NaN",
    ]
    
    actual_urls = []
    for m in msgs:
        print(m.request.url)
        actual_urls.append(m.request.url)
        # print(m.response.status_code)
    
    for expected_url in expected_urls:
        assert expected_url in actual_urls, f"Expected URL {expected_url} not found in output"
