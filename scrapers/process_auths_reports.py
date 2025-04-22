from johnllm import LMP
from pathlib import Path

from .utils import AuthNZVulnInfo, process_reports_in_batches

class CategorizeReports(LMP):
    prompt = """
{{report}}

Okay here are two proposed metholodogies for finding a certain class of authN/authZ bugs: * *
Vulnerability Name: IDOR 
- checking every combination of (user_id, action, resource_id) possible. For example this could be user A editing the invite link for a chat room (via POST /room/<room_id>) created by user B. this represents the basic IDOR vulnerability class
* Detection Method: collecting (user_a, action, resource_id) pair via HTTP requests (that is, requests using user_a's authenticated session), swapping out the original user_a for user_b, a non-privledged (in this case, an user_id that should not have access to the resource_id) user and testing if the resource authorization boundary can be crossed
Vulnerability Name: AuthN/AuthZ Bypass
- given a session/no session, a user is able to access a page or functionality that they should not be able to access ie. regular user accessing the admin panel. so similar to the above, but this time, the authorization boundary being crossed is at a functional/usage level. this would include openredirect vulns where access is granted to page normally closed off to the user by using the redirect URL
* Detection Method: collecting (user_a, action) or (user_a, navigation), and swapping out the original user_a for user_b, a non-privledged user, and testing if the action/navigation authorization boundary can be crossed

Give your answer to indicate if the report above is detectable using the methodologies proposed
"""
    response_format = AuthNZVulnInfo

if __name__ == "__main__":
    process_reports_in_batches(reports_dir=Path("scrapers/high_reports"), lmp=CategorizeReports, batch_size=50, max_workers=20)
