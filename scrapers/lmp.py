from johnllm import LMP
from pydantic import BaseModel
from typing import Optional, List, Tuple
from enum import Enum

class AuthNZMetadata(BaseModel):
    reason: str
    is_detectable: bool

class AuthNZStruct(BaseModel):
    authnz_metadata: AuthNZMetadata

class CategorizeInjections(LMP):
    prompt = """
{{report}}

Okay here are two proposed metholodogies for finding a certain class of authN/authZ bugs: 
Vulnerability Name: IDOR 
- checking every combination of (user_session, action, resource_id) possible. For example this could be user A editing the invite link for a chat room (via POST /room/<room_id>) created by user B. this represents the basic IDOR vulnerability class
* Detection Method: collecting (user_a, action, resource_id) pair via HTTP requests (that is, requests using user_a's authenticated session), swapping out the original user_a for user_b, a non-privledged (in this case, an user_id that should not have access to the resource_id) user and testing if the resource authorization boundary can be crossed

Vulnerability Name: AuthN/AuthZ Bypass
- given a session/no session, a user is able to access a page or functionality that they should not be able to access ie. regular user accessing the admin panel. so similar to the above, but this time, the authorization boundary being crossed is at a functional/usage level. this would include openredirect vulns where access is granted to page normally closed off to the user by using the redirect URL
* Detection Method: collecting (user_a, action) or (user_a, navigation), and swapping out the original user_a for user_b, a non-privledged user, and testing if the action/navigation authorization boundary can be crossed

The naive application of the above two methodologies look like this.
1. User navigates the website *regularly* (without intending to trigger any vulnerable behaviour)
2. All HTTP requests/responses are logged
3. A program analyzes the requests and responses to extract (user_session, action, resource_type::resource_id) tuples
*Note: resource_type::resource_id denotes a resource_id of a certain type (ie. project_id::1234)
4. By collecting these tuples for each response, the software automatically performs the above two methodologies as follows:
a) store (user_session, action, resource_id) tuples
b) for each new action, execute with all existing user_sessions AND all matching resource_ids of the same resource_type (Authz, IDOR)
c) for each new user_session, execute each action with the new user_session (AuthZ, IDOR)
d) for each new action, execute with unauthenticated user session (AuthN)
e) for each new resource_id of an existing resource_type, substitute the resource_id with the new resource_id and execute it with existing users (Authz, IDOR)

Here are some examples:

<example_vuln1>
Steps to Reproduce:
1. Login to the attacker's account (attacker@email.com)
2. Navigate to the Update Profile section in the attacker's account
3. Change the attacker's email to the victim's email (victim@email.com)
4. Attempt to login to the victim's account (victim@email.com)
5. Observe that the victim can no longer login due to 'Invalid Credentials'

<reason>
- update email is a request that is executed in normal flow
- swapping resource_ids (the email) with existing (action, resource_id) is covered by test e) 
</reason>

Detectable: True
</example_vuln1>

<example_vuln2>
Steps to Reproduce:
1. Identify the unique email address format for creating GitLab issues via email: incoming+(username)/(projectname)+(token)@gitlab.com.
2. Use this email address to sign up for Slack or other services that accept @gitlab.com email addresses for verification.
3. Check the issue created in your GitLab project for the verification email from the service (e.g., Slack).
4. Click the verification link in the email to complete the sign-up process and gain access to the service as a verified GitLab team member.

<reason>
- since Slack and Github are indenpedent applications, none of the steps would apply since they deal with user_session/user_ids scoped to the same applicaiton
</reason>

Detectable: False
</example_vuln2>

Your task is to determine if the report can found using the methodology above
First respond with your reasoning, then with whether or not you think it's detectable
"""
    response_format = AuthNZStruct


class InjectionMetadata(BaseModel):
    is_simple_payload: bool

class InjectionStruct(BaseModel):
    injection_metadata: InjectionMetadata 

class CategorizeAuthNZ(LMP):
    prompt = """
{{report}}

Okay here is a proposed methodology for finding a class of bugs. 
# Simple Payloads
1. Find every injectable parameter on a webpage.
2. Then using a *simple* payload list that contains common permutations of payloads such as b64 encoding, context positioning for XSS, etc.,
inject the payload into the parameter and send the request
-> *simple* means a generic payload that does not include any kind of custom filter bypass
3. Payload execution can be determined within the same channel ie. for blind SQLi payloads, there is usually some way
to detect the response

Return your answer as a boolean called is_simple_payload
"""
    response_format = InjectionStruct


class MiscCategories(BaseModel):
    requires_code: bool
    requires_CVE: bool
    is_ctf: bool
    other_report: Optional[str]

class CategorizeMisc(LMP):
    prompt = """
{{report}}

Given the report above, extract the following information:

requires_code: does part of the vulnerability discovery involve looking at the source code of the *backend application*?
If so, return True. Note that client-side JS code/scripts (unless its something like node) is not considered backend code
requires_CVE: does the vulnerability require a CVE to be exploited
is_ctf: is this a ctf challenge
other_report: does the writeup explicitly mention another Hackerone report? If so, put the report ID in; otherwise null
"""
    response_format = MiscCategories


class Level(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


# TODO: once labeled, run again with all examples
# to rank them in order of complexity
class VulnClassification(BaseModel):
    steps: List[Tuple[int, str]]
    vuln_description: str
    reason: str
    new_complexity: Level

class CategorizeReports(LMP):
    prompt = """
REPORT:
{{report}}

You are asked to classify the discovery difficulty of a vulnerability report, that is, how difficult would it have been for the tester to discover this
vulnerability? The contribution to discovery difficulty can be separated into two categories:
- the attack includes multiple components, which requires the attacker to remember context for each one when formulating the attack
- the attack includes subtle/non-obvious interactions between the components
- the attack includes manipulating complex application states
- the attack includes novel logic that is not commonly found in other applications

Your output should include the following:
- A list of steps to reproduce the vulnerability. You should rewrite this if the original instructions were unclear
- a description of the vulnerability
- reason for complexity classification
- the complexity of the vulnerability (LOW, MEDIUM, HIGH, VERY_HIGH)

Here are some examples:
<example1>
Vulnerability Summary
This is an information disclosure and authentication bypass vulnerability in Shopify's internal system (athena-flex-production.shopifycloud.com). Though the site normally redirects users to Okta login, the initial page load exposes JavaScript files before the redirect occurs. By analyzing these JavaScript files, the researcher discovered a GraphQL endpoint that allows unauthenticated access to sensitive Zendesk ticket information.

Steps to Reproduce
Observe that athena-flex-production.shopifycloud.com loads momentarily before redirecting to Okta
Using view-source in Chrome, examine the initial page content: view-source:athena-flex-production.shopifycloud.com
Locate the JavaScript source file in the page source:
https://cdn.shopifycloud.com/athena-flex/assets/main-3fe2559f5e86bcc7d88fe611b71942faa73e787afbc2126a601662ab254a36fc.js

Beautify and analyze the JS to identify the GraphQL endpoint structure
Send a targeted GraphQL query directly to the endpoint:
curl -X POST \
  -H 'Content-Type: application/json' \
  --data-binary '{"query": "query getRecentTicketsQuery($domain: String) {\n shop(myshopifyDomain: $domain) {\n zendesk {\n tickets(last: 5) {\n edges {\n node {\n id\n requester {\n name\n }\n subject\n description\n }\n }\n }\n }\n }\n }\n","variables":{"domain":"ok.myshopify.com"}}' \
  'https://athena-flex-production.shopifycloud.com/graphql'

Receive unrestricted access to Zendesk ticket information in the response
</example1>
<complexity>
state_complexity: MEDIUM
reason: While this vulnerability involves several components - the JS script, GraphQL, zendesk - and the JS file that disclosed the endpoints was part of a
complex authentication redirect, but the remainder of the attack was straightforward once the GraphQL endpoint was discovered 
</complexity>

<example2>
Vulnerability Summary
This vulnerability allows a regular GitLab user to gain administrator privileges when an administrator uses the impersonation feature to access their account. The issue occurs because the impersonated user can access and hijack the administrator's impersonation session, then exit the impersonation mode to gain the administrator's original privileges.
Steps to Reproduce

Login to GitLab as a normal user (the "attacker")
Navigate to the Active Sessions settings tab
Revoke all sessions except your current active session
Have a GitLab administrator login (in a different browser) and impersonate your account
As the attacker, refresh your Active Sessions page - you'll now see a second active session (this is the administrator's impersonation session)
Inspect the "Revoke" button for this second session and copy the session ID
Navigate to the GitLab homepage (http://gitlab.bb/ in the example)
Clear your browser cookies
Open developer console and manually set the GitLab session cookie to the copied session ID:
javascriptdocument.cookie = "_gitlab_session=SESSION_ID_HERE";

Refresh the page - you are now in the administrator's impersonation session
Click "Stop impersonating" in the top-right corner
You now have full administrator access to GitLab
</example2>
<complexity>
state_complexity: HIGH
reason: This vulnerability involves understanding how the session impersonation feature works in different contexts, one from the user side
and one from the admin side. It also contains a non-obvious interaction logic between the impersonated and impesonator, namely that the current session
id of the impersonator would be saved and stored on the client side, and readable to the impersonated user
</complexity>

<example3>
Vulnerability Summary
This vulnerability lets any Shopify Partner grant themselves active collaborator access to a merchant's store without the merchant approving the request.
The flaw is in the "auto-convert" routine that is supposed to convert an existing normal user who is already trusted on the store into a collaborator.
Because the routine merely checks for "any user record with the same e-mail" and does not verify the record's type (normal vs collaborator) or status (active vs pending), an attacker can:
create a pending collaborator record for Store S, and
immediately trigger the auto-conversion again with the same e-mail,
causing that pending record to be flipped to status = active, granting full collaborator privileges - no action from the merchant is ever required.

Steps to Reproduce
Create the pending record (attacker Account A)
Log in to the Partner Dashboard (or create a Partner account) with e-mail attacker@example.com.
Under Stores -> Add store access, request collaborator access to the target merchant store Store S.
Observe that the request now shows "Pending approval" in your Partner dashboard.
Trigger the faulty auto-convert (attacker Account B)
Log out or open a second browser/session.
Create another Partner account (or simply a second collaborator request) that uses the same e-mail attacker@example.com.
Again request collaborator access to Store S.
Observe the automatic approval
Refresh either Partner account's Stores page.
The previously pending request now shows "Active" - you have collaborator access to Store S even though the merchant never acted on it.
Validate access
Click Log in to store from the Partner dashboard.
You land inside Store S's admin interface with full collaborator privileges (as configured in the request).
</example3>
<complexity>
state_complexity: VERY_HIGH
This vulnerability requires the attacker to understand:
- differences between normal store user and collaborator
- the existence of the auto-convert routine
- the very subtle logic flaw that checks for *any* user regardless of pending/active status before auto-approving a collborator
</complexity>

Now give your answer to the question:
You are asked to classify the discovery difficulty of a vulnerability report, that is, how difficult would it have been for the tester to discover this
vulnerability? The contribution to discovery difficulty can be separated into two categories:
- the attack includes multiple components, which requires the attacker to remember context for each one when formulating the attack
- the attack includes subtle/non-obvious interactions between the components
- the attack includes manipulating complex application states
- the attack includes novel logic that is not commonly found in other applications

Your output should include the following:
- a list of steps to reproduce the vulnerability
- a description of the vulnerability
- reason for complexity classification
- the complexity of the vulnerability (LOW, MEDIUM, HIGH, VERY_HIGH)
"""
    response_format = VulnClassification

class VulnCategory(str, Enum):
    WEB_APP = "WEB_APP"
    API = "API" 
    MOBILE = "MOBILE"
    IOT = "IOT"
    CODE = "CODE"

class Report(BaseModel):
    category: VulnCategory

class CategorizeVuln(LMP):
    prompt = """
{{report}}

The above is a report for a vulnerability. Please categorize it into one of the following categories:

WEB_APP:  a vuln in *deployed* software. a network vulnerability that requires some interaction with a user interface (that is, this is not *strictly* required since the interface action may be triggered by an API call but the in the report the finding originates from the interface)
API: a vuln in *deployed* software. a network vulnerability that does not require some interaction with a user interface
MOBILE: all mobile originating vulnerabilities
IOT: all IOT vulns should be here, including random hardware things
CODE: the vulnerability exists *intrinsically* in some software package, rather than a deployed application. all new vulnerabilities should be categorized here. the exploitation of existing vulns in * deployed* software should either go under API or WEB_APP
"""
    response_format = Report
