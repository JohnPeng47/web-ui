from johnllm import LLMModel, LMP
from typing import List, Tuple
from pydantic import BaseModel
from enum import Enum
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from random import shuffle
import time

from .utils import process_reports_in_batches

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

if __name__ == "__main__":
    process_reports_in_batches(Path("scrapers/high_reports"), CategorizeReports, batch_size=50, max_workers=20)
