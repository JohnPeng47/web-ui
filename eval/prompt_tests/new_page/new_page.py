from src.agent.discovery import DetermineNewPage
from src.llm_models import openai_4o, cohere_command_a

MSGS = """
Here is the current page:
URL: http://147.79.78.153:3000/#/
Contents:
[0]<div />
OWASP Juice Shop
Account
[1]<a exit_to_app
Login/>
Contact
[2]<a feedback
Customer Feedback/>
Company
[3]<a business_center
About Us/>
[4]<a camera
Photo Wall/>
[5]<a school
Help getting started/>
[6]<a GitHub/>
OWASP Juice Shop
v17.3.0
[7]<div />
menu
OWASP Juice Shop
search
language
All Products
Apple Juice (1000ml)
1.99¤
Apple Pomace
0.89¤
Banana Juice (1000ml)
1.99¤
Only 1 left
Best Juice Shop Salesman Artwork
5000¤
[8]<img />
Carrot Juice (1000ml)
2.99¤
[9]<img />
Eggfruit Juice (500ml)
8.99¤
[10]<img />
[11]<img />

Here is the previous page:
URL: http://147.79.78.153:3000/#/
Contents:
[0]<button menu/>
[1]<button OWASP Juice Shop/>
[2]<img />
search
[3]<button language
EN/>
All Products
[4]<img />
Apple Juice (1000ml)
1.99¤
[5]<img />
Apple Pomace
0.89¤
[6]<img />
Banana Juice (1000ml)
1.99¤
Only 1 left
[7]<img />
Best Juice Shop Salesman Artwork
5000¤
[8]<img />
Carrot Juice (1000ml)
2.99¤
[9]<img />
Eggfruit Juice (500ml)
8.99¤
[10]<img />
[11]<img />

Here is the previous goal that resulted in a transition to the current page:
Since the navigation and verification are complete, there is no further action required for this task.

Here is the homepage:
URL: http://147.79.78.153:3000/#/
Contents:
[0]<button menu/>
[1]<button OWASP Juice Shop/>
[2]<img />
search
[3]<button language
EN/>
All Products
[4]<img />
Apple Juice (1000ml)
1.99¤
[5]<img />
Apple Pomace
0.89¤
[6]<img />
Banana Juice (1000ml)
1.99¤
Only 1 left
[7]<img />
Best Juice Shop Salesman Artwork
5000¤
[8]<img />
Carrot Juice (1000ml)
2.99¤
[9]<img />
Eggfruit Juice (500ml)
8.99¤
[10]<img />
[11]<img />

Now try to determine if the current page is a:
- new_page: a completely different page from the *homepage* but still part of the same web application
- subpage: a different view of the homepage (ie. popup, menu dropdown, etc.)
- out_of_scope: a completely different website from the *homepage*

Some guidance:
- when picking the name for a subpage, try to pick something descriptive of the new view that is introduced in the subpage from the previous page

Now answer with the status of the current page
        
Understand the content and provide
the parsed objects in json that match the following json_schema:
{
  "$defs": {
    "NewPageStatus": {
      "enum": [
        "new_page",
        "no_change",
        "subpage",
        "out_of_scope"
      ],
      "title": "NewPageStatus",
      "type": "string"
    }
  },
  "properties": {
    "name": {
      "title": "Name",
      "type": "string"
    },
    "status": {
      "$ref": "#/$defs/NewPageStatus"
    }
  },
  "required": [
    "name",
    "status"
  ],
  "title": "NavPage",
  "type": "object"
}

Make sure to return an instance of the JSON, not the schema itself
"""

for i in range(10):
    nav_page = DetermineNewPage().invoke_with_msgs(
        model=openai_4o,
        msgs=MSGS
    )
    print(nav_page)

