import requests

base_url = "http://127.0.0.1:8000"
# engagement_id = "aa0a1765-920d-4e03-b715-2d179e50c0ab"

# get_agents_resp = requests.get(f"{base_url}/engagement/{engagement_id}/agents")
# assert get_agents_resp.status_code == 200
# agents_list = get_agents_resp.json()

exploit_agent_id = "ad6d49ea-76d4-40dd-aa50-b24d808b2d9f"
get_agents_resp = requests.get(f"{base_url}/agents/{exploit_agent_id}/steps")
assert get_agents_resp.status_code == 200
steps_list = get_agents_resp.json()

print(steps_list)