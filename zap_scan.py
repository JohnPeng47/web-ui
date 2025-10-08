import json

a = """
{
  "evaluation_previous_goal": "Successfully clicked 'ACCESS THE LAB', which redirected to a login page in Tab 0 as expected.",
  "next_goal": "Switch to Tab 0 (the login page), enter the provided username and password credentials, and attempt to log in.",
  "action": [
    {"switch_tab": {"page_id": 0}},
    {"input_text": {"index": 1, "text": "johnpeng47@gmail.com"}},
    {"input_text": {"index": 2, "text": "!Gdn565x03]BX77R,qmND5SBQ.|Yq6}+"}},
    {"click_element_by_index": {"index": 3, "new_tab": false}}
  ]
}
"""



print(json.loads(a).__repr__())