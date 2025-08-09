from src.llm_provider import LMP
from pydantic import BaseModel
from typing import List

from enum import Enum

class VulnCategory(str, Enum):
    SQL_INJECTION = "sql_injection"
    CROSS_SITE_SCRIPTING = "cross_site_scripting"
    CROSS_SITE_REQUEST_FORGERY = "cross_site_request_forgery"
    CLICKJACKING = "clickjacking"
    DOM_BASED_VULNERABILITIES = "dom_based_vulnerabilities"
    CROSS_ORIGIN_RESOURCE_SHARING = "cross_origin_resource_sharing"
    XML_EXTERNAL_ENTITY_INJECTION = "xml_external_entity_injection"
    SERVER_SIDE_REQUEST_FORGERY = "server_side_request_forgery"
    HTTP_REQUEST_SMUGGLING = "http_request_smuggling"
    OS_COMMAND_INJECTION = "os_command_injection"
    SERVER_SIDE_TEMPLATE_INJECTION = "server_side_template_injection"
    PATH_TRAVERSAL = "path_traversal"
    ACCESS_CONTROL_VULNERABILITIES = "access_control_vulnerabilities"
    AUTHENTICATION = "authentication"
    WEB_SOCKETS = "web_sockets"
    WEB_CACHE_POISONING = "web_cache_poisoning"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    INFORMATION_DISCLOSURE = "information_disclosure"
    BUSINESS_LOGIC_VULNERABILITIES = "business_logic_vulnerabilities"
    HTTP_HOST_HEADER_ATTACKS = "http_host_header_attacks"
    OAUTH_AUTHENTICATION = "oauth_authentication"
    FILE_UPLOAD_VULNERABILITIES = "file_upload_vulnerabilities"
    JWT = "jwt"
    ESSENTIAL_SKILLS = "essential_skills"
    PROTOTYPE_POLLUTION = "prototype_pollution"
    GRAPHQL_API_VULNERABILITIES = "graphql_api_vulnerabilities"
    RACE_CONDITIONS = "race_conditions"
    NOSQL_INJECTION = "nosql_injection"
    API_TESTING = "api_testing"
    WEB_LLM_ATTACKS = "web_llm_attacks"
    WEB_CACHE_DECEPTION = "web_cache_deception"
    OTHER = "other"

class ClassifyVulnLM(BaseModel):
    vuln_category: List[VulnCategory]


class ClassifyVuln(LMP):
    prompt = """
{{vuln_description}}

Tag the vulnerability with the most relevant vuln category
Aim for single tag
Two tags are okay
Three tags are overdoing it, very rare

Now tag it
"""
    response_format = ClassifyVulnLM