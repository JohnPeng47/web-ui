from src.agent.http_history import HTTPHandler
import pytest

# TODO: still something wrong with filtering, get to bottom of this tmrw
# nvm seems to be working... confirm in more detail tmrw
@pytest.mark.asyncio
async def test_filter_scope(http_msgs):
    http_handler = HTTPHandler(
        scopes=[
            "http://147.79.78.153:3000/rest/",
            "http://147.79.78.153:3000/api/",
        ]
    )

    print(len(http_msgs))
    for r in http_msgs:
        req, res = r.request, r.response
        await http_handler.handle_request(req)
        await http_handler.handle_response(res, req)

    msgs = await http_handler.flush()

    print("FLUSHED")
    for m in msgs:
        print(m.request.url)
        # print(m.response.status_code)
