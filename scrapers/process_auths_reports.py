from johnllm import LMP
from pathlib import Path

from .utils import AuthNZStruct, process_reports_in_batches

class CategorizeReports(LMP):
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

if __name__ == "__main__":
    process_reports_in_batches(reports_dir=Path("scrapers/high_reports"), lmp=CategorizeReports, batch_size=50, max_workers=20)
