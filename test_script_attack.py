from johnllm import LMP

class ScriptAttack(LMP):
    prompt = """
{{attack_info}}

Given the description above, you are tasked with constructing an attack by generating a python script
Here are some limitations:
- the attack should only focus on the HTTP requests/responses with this single URL endpoint. accessing other endpoints
is out of scope
- the attack should focus on generating/parsing a single/series of HTTP requests/responses

<% if attack_history %>
Here is a history of your attempts so far:
{{attack_history}}
<% endif %}                                                                 
"""