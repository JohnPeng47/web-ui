import requests
import time

base_url = "http://127.0.0.1:8000"

# 2. Create engagement (API)
engagement_payload = {
    "name": "Discovery Agent Integration Test",
    "base_url": "http://147.79.78.153:3000/#/login",
    "description": "Integration test for discovery agent functionality",
    "scopes_data": [
        "http://147.79.78.153:3000/rest/",
        "http://147.79.78.153:3000/api/",
    ],
}
create_resp = requests.post(f"{base_url}/engagement/", json=engagement_payload)
assert create_resp.status_code == 200
engagement = create_resp.json()
engagement_id = engagement["id"]
print("Engagement created: ", engagement_id)

# 3. Register discovery agent (API)
agent_payload = {
    "start_urls": [
        "http://147.79.78.153:3000/#/login",
        "http://147.79.78.153:3000/#/contact",
        "http://147.79.78.153:3000/#/search"
    ]
}
register_resp = requests.post(
    f"{base_url}/engagement/{engagement_id}/agents/discovery/register",
    json=agent_payload,
)
# assert register_resp.status_code == 200
agent = register_resp.json()
agent_id = agent["id"]
