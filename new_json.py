import json

data = json.loads(open("scripts/portswigger/port_swigger_labs.json", "r", encoding="utf-8").read())

# List of server-side vulnerabilities identified in the Web Security Academy
server_side_vulnerabilities = [
    "sql_injection",
    "authentication",
    "path_traversal",
    "os_command_injection",
    "business_logic_vulnerabilities",
    "information_disclosure",
    "access_control_vulnerabilities",
    "file_upload_vulnerabilities",
    "race_conditions",
    "server_side_request_forgery",
    "xml_external_entity_injection",
    "nosql_injection",
    "api_testing",
    "web_cache_deception"
]

# Create a new JSON with only server-side vulnerabilities
server_side_data = {}
for key in server_side_vulnerabilities:
    if key in data:
        server_side_data[key] = data[key]
    else:
        # Handle potential mapping differences between our list and the JSON keys
        # For example, "xml_external_entity_injection" might be stored as "xxe"
        # Try to find alternative keys
        if key == "authentication" and "authentication" in data:
            server_side_data["authentication"] = data["authentication"]
        elif key == "server_side_request_forgery" and "ssrf" in data:
            server_side_data["server_side_request_forgery"] = data["ssrf"]
        elif key == "xml_external_entity_injection" and "xml_external_entity_injection" not in data and "xxe" in data:
            server_side_data["xml_external_entity_injection"] = data["xxe"]
        elif key == "access_control_vulnerabilities" and "access_control" in data:
            server_side_data["access_control_vulnerabilities"] = data["access_control"]

# Convert to JSON
server_side_json = json.dumps(server_side_data, indent=2)

# Print the result
print(server_side_json)