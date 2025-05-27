GENERIC_SUBSET = [
    # {"vuln_name": "path_traversal", "labs": [0,1,2,3,4,5]},
    {"vuln_name": "sql_injection", "labs": [2,5,6,17]},
    {"vuln_name": "path_traversal", "labs": [2,3]},
    {"vuln_name": "server_side_request_forgery", "labs": [1]}
]

SQLI_SUBSET = [
    {"vuln_name": "sql_injection", "labs": [2,5,6,17]},
]

SQLI_SUBSET_NO_STATE = [
    {"vuln_name": "sql_injection", "labs": [2,3,4,5,6,8,9]}   
]

SQLI_TEST = [
    {"vuln_name": "sql_injection", "labs": [8]}   
]