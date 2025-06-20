from src.agent.discovery import DetermineNewPage
from src.llm_models import openai_4o, cohere_command_a

MSGS = """
Here is the current page:
URL: http://147.79.78.153:3000/#/search
Contents:
[0]<div />
OWASP Juice Shop
Contact
[1]<a feedback
Customer Feedback/>
Company
[2]<a business_center
About Us/>
[3]<a camera
Photo Wall/>
[4]<a school
Help getting started/>
[5]<a GitHub/>
OWASP Juice Shop
v17.3.0
[6]<div />
menu
OWASP Juice Shop
search
account_circle
Account
language
EN
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
Carrot Juice (1000ml)
2.99¤
Eggfruit Juice (500ml)
8.99¤
Fruit Press
89.99¤
Green Smoothie
1.99¤
Only 1 left
[7]<img />
Juice Shop "Permafrost" 2020 Edition
9999.99¤
[8]<img />
Lemon Juice (500ml)
2.99¤
Only 3 left
[9]<img />
Melon Bike (Comeback-Product 2018 Edition)
2999¤
Sold Out
[10]<img />
OWASP Juice Shop "King of the Hill" Facemask
13.49¤
Items per page:
[11]<mat-select 12/>
1 – 12 of 36
[12]<button />
[13]<button />

Here is the previous page:
URL: 
Contents:


Here is the previous goal that resulted in a transition to the current page:


Here is the homepage:
URL: http://147.79.78.153:3000/#/
Contents:
[0]<button menu/>
[1]<button OWASP Juice Shop/>
[2]<img />
search
[3]<button account_circle
Account/>
[4]<button language
EN/>
All Products
[5]<img />
Apple Juice (1000ml)
1.99¤
[6]<img />
Apple Pomace
0.89¤
[7]<img />
Banana Juice (1000ml)
1.99¤
Only 1 left
[8]<img />
Best Juice Shop Salesman Artwork
5000¤
[9]<img />
Carrot Juice (1000ml)
2.99¤
[10]<img />
Eggfruit Juice (500ml)
8.99¤
[11]<img />
Fruit Press
89.99¤
[12]<img />
Green Smoothie
1.99¤
Only 1 left
[13]<img />
Juice Shop "Permafrost" 2020 Edition
9999.99¤
[14]<img />
Lemon Juice (500ml)
2.99¤
Only 3 left
[15]<img />
Melon Bike (Comeback-Product 2018 Edition)
2999¤
Sold Out
[16]<img />
OWASP Juice Shop "King of the Hill" Facemask
13.49¤
Items per page:
[17]<mat-select 12/>
1 – 12 of 36
[18]<button />
[19]<button />

Now try to determine if the current page is a:
- new_page: a completely different page from the *homepage* but still part of the same web application
- subpage: a different view of the homepage (ie. popup, menu dropdown, etc.)
- out_of_scope: a completely different website from the *homepage*

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
        model=cohere_command_a,
        msgs=MSGS
    )
    print(nav_page)

