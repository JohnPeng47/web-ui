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
    ]
}
create_resp = requests.post(f"{base_url}/engagement/", json=engagement_payload)
assert create_resp.status_code == 200
engagement = create_resp.json()
engagement_id = engagement["id"]
print("Engagement created: ", engagement_id)

# 3. Register discovery agent (API)
agent_payload = {
    "max_steps": 5,
    "model_name": "gpt-4o-mini",
    "model_costs": 0.01,
    "log_filepath": "/tmp/discovery_agent.log",
}
register_resp = requests.post(
    f"{base_url}/engagement/{engagement_id}/agents/discovery/register",
    json=agent_payload,
)
# assert register_resp.status_code == 200
agent = register_resp.json()
agent_id = agent["id"]
print(agent)

# # 4. Continue polling on the agent page_data API on a poll/sleep(1) loop for 20 iterations
page_data_found = False
for i in range(30):
    get_page_data_resp = requests.get(f"{base_url}/agents/{engagement_id}/page-data")
    assert get_page_data_resp.status_code == 200
    page_data_result = get_page_data_resp.json()
    print(page_data_result)
    
    if "page_data" in page_data_result and page_data_result["page_data"]:
        page_data_found = True
        break
        
    time.sleep(2)

# 5. Confirm that the page data is not empty and has been updated by the agent
assert page_data_found, "Discovery agent did not collect any page data within 20 seconds"

# Verify the structure of collected page data
final_resp = requests.get(f"{base_url}/agents/{agent_id}/page-data")
final_data = final_resp.json()
