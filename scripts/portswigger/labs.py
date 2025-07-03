GENERIC_SUBSET = [
    {"vuln_name": "sql_injection", "labs": [2,5,8]},
    {"vuln_name": "server_side_request_forgery", "labs": [1]},
    {"vuln_name": "path_traversal", "labs": [2]},
    {"vuln_name": "file_upload", "labs": [4]}
]

SQLI_SUBSET = [
    {"vuln_name": "sql_injection", "labs": [2,5,6,17]},
]

SQLI_SUBSET_NO_STATE = [
    {"vuln_name": "sql_injection", "labs": [2,3,4,5,6,8,9]}   
]

SQLI_TEST = [
    {"vuln_name": "sql_injection", "labs": [2,5,8]}   
]

SSRF_TEST_SINGLE = [
    {"vuln_name": "server_side_request_forgery", "labs": [1]},
]

XSS_TEST_SINGLE = [
    {"vuln_name": "cross_site_scripting", "labs": [2]},
]