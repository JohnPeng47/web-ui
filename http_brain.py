from httplib import HTTPMessage, HTTPRequest, parse_burp_xml

import json
import os
from pydantic import BaseModel, Field
from johnllm import LLMModel, LMP
from typing import List, Optional, Dict
from enum import Enum

# TODO: create an ExtractInjectionInformation request that takes into account the webpage context
class ResourceType(BaseModel):
    name: str
    description: str
    # TODO: still need to decide on a unique way of identifying requests
    requests: List[str] = Field(default_factory=list)
    
    def to_prompt_str(self):
        return f"Resource Type: {self.name}\nDescription: {self.description}\n"
    
class RequestPart(str, Enum):
    URL = "URL"
    BODY = "BODY"
    HEADERS = "HEADERS"
    
class Resource(BaseModel):
    id: str
    type: ResourceType
    request_part: RequestPart
    selected_slice: Dict[RequestPart, str] = Field(default_factory=dict)
    
class UserID(BaseModel):
    id: str
    request_part: RequestPart
    selected_slice: Dict[RequestPart, str] = Field(default_factory=dict)

class RequestInfo(BaseModel):
    resources: Optional[List[Resource]] = Field(default_factory=list)
    user_ids: Optional[List[UserID]] = Field(default_factory=list)

# {% if resource_types %}
# Existing Resources:
# {{ resource_types }}
# {% endif %}

# TODO: support parameter in headers
# TODO: we should support parsing response for a returned id as well
# TODO: add tests for the following
# - the parameter occuring in multiple places
class ExtractAuthInformation(LMP):
    prompt = """
{{request}}

You are given an HTTP request.
Your task is to extract the following information from the request:

1. resources
These request parameters represent a resource used in the application.
For example:
- A request to "/api/posts/456/comments" likely represents a comment resource related to post "456"
- A request to "/api/data" with JSON payload {"user": {"name": "John"}} likely represents a user resource

{% if resource_types %}
Does the resource match any of the existing resource types? If so then select that type
{% endif %}

If this is a new resource, then create it
Be careful to differentiate resource names from actions and parameters

2. user_ids
These request parameters represent user IDs that are used in the application

When returning the identified resource_ids and user_ids, please provide the selected_slice parameter, which identifies the specific position
of the resource in the request. The way you should give this data is to:
1. Take the surrounding of the resource/user_id, but make sure to not step across request element boundaries ie. if param in URL do not include the headers in surround
2. Next identify where in the request the resource/user_id is located by the following steps:
Identify whether its in the URL, BODY, or HEADERS:
NOTE: SEPARATOR = "$%&" ie. /post/$%&user1234$%&/comments
    if URL:
        - return selected_slice as the URL where selected resource/user_id value is enclosed within the SEPARATOR
        ie. /post/$%&user1234$%&/comments
        ie. /tweets?id=1234
    elif BODY:
        - return selected_slice as the name of body field
    elif HEADERS:
        - return selected_slice as {}

Here are some examples:
1. GET http://localhost:8000/tweets/list/
{
    "resources": []
    "user_ids": []
}

2. GET http://localhost:8000/messages/
{
    "resources": []
    "user_ids": []
}

3. GET http://twitter.com/api/tweets/2/replies/
{
    "resources": [
        {
            "id": "2",
            "type": {
                "name": "tweet_reply",
                "description": "This represents replies to a tweet, determined by the endpoint '/api/tweets/{tweet_id}/replies/'.",
                "requests": []
            },
            "request_part": "URL",
            "selected_slice": {
                "URL": "/api/tweets/$%&2$%&/replies/"
            }
        }
    ],
    "user_ids": null
}

4. POST http://twitter.com/reply/
{'csrfmiddlewaretoken': 'h0EclP8OYE80II6kTnXGYgTqiyFPhTBxl3FPTOat7YxJuc9tnjV4qV2g37zmFle1', 'tweet': 'tw121345', 'hashtags': '#twitter', 'media_id': '', 'reply_to': '11', 'visibility': 'public', 'location': '1', 'notes': 'test tweet'}

{
    "resources": [
        {
            "id": "tw121345",
            "type": {
                "name": "tweet",
                "description": "Represents a tweet being created",
                "requests": []
            },
            "request_part": "BODY",
            "selected_slice": {
                "BODY": "tweet"
            }
        },
    ],
    "user_ids": []
}

Now give your answer
"""
    response_format = RequestInfo

def url_to_name(url: str, seen_names: List) -> str:
    """
    Convert a URL to a name by removing the protocol and replacing slashes with underscores.
    """
    name = url.replace("http://", "").replace("https://", "").replace("/", "_")
    if name in seen_names:
        name = f"{name}_{len(seen_names)}"

    seen_names.append(name)    
    return name.replace(":", "")


# TODO: need to work on prompt, confused 3 for user rather than order
if __name__ == "__main__":
    BURP_REQUESTS = "histories/burp_requests/test_vulnweb"
    OUTPUT_DIR = "histories/labeled_requests"
    seen_names = []

    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    msgs = parse_burp_xml(BURP_REQUESTS)
    for m in msgs:
        req_str = m.request.to_str()
        model = LLMModel()
        auth_info = ExtractAuthInformation().invoke(
            model,
            model_name="gpt-4o",
            prompt_args={"request": req_str},
        )
        filename = url_to_name(m.request.url, seen_names)
        output_path = os.path.join(OUTPUT_DIR, f"{filename}.json")

        print(f"Writing to {output_path} ...")

        # Write the structured data as a single JSON object
        with open(output_path, "w") as f:
            f.write(req_str)
            f.write("\n")
            f.write(json.dumps(auth_info.dict(), indent=4))

#     request = """
# [Request]: POST http://localhost:8000/orders/create/
# {'host': 'localhost:8000', 'content-length': '147', 'cache-control': 'max-age=0', 'sec-ch-ua': '"Chromium";v="135", "Not-A.Brand";v="8"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'accept-language': 'en-US,en;q=0.9', 'origin': 'http://localhost:8000', 'content-type': 'application/x-www-form-urlencoded', 'upgrade-insecure-requests': '1', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36', 'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7', 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'navigate', 'sec-fetch-user': '?1', 'sec-fetch-dest': 'document', 'referer': 'http://localhost:8000/orders/create/', 'accept-encoding': 'gzip, deflate, br', 'cookie': 'csrftoken=edbNI9cPjuzTWEdjE68yCPj0VJ4HyCNE; sessionid=aremi6hp8o2mh26gbtgv1lsiuym8eqcx', 'connection': 'keep-alive'}
# {'csrfmiddlewaretoken': 'HWNMVs9AWYLw3tuOYbbYPsoPTEUCX1YBLZOptrbf5iafPXxXs79mh7xFEdO9ltB5', 'customer': '3', 'shipping_address': 'EG', 'billing_address': 'WWGE', 'notes': 'GWGE'}
# """
