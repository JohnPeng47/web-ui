from src.agent.discovery import UpdatePlanNested
from src.llm_models import (
  openai_4o, 
  cohere_command_a, 
  openai_41,
  gemini_25_flash
)

MSG = """
You are performing QA testing on a web application. Your task is to uncover/explore all user flows of the application
    
Here is the current webpage:
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
[7]<img />
Fruit Press
89.99¤
[8]<img />
Green Smoothie
1.99¤
Only 1 left
[9]<img />
Juice Shop "Permafrost" 2020 Edition
9999.99¤

Here is the previous webpage:
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
Best Juice Shop Salesman Artwork
5000¤
Carrot Juice (1000ml)
2.99¤
Eggfruit Juice (500ml)
8.99¤
[8]<img />
Fruit Press
89.99¤
[9]<img />
Green Smoothie
1.99¤
Only 1 left
[10]<img />
Juice Shop "Permafrost" 2020 Edition
9999.99¤

Here is the previous plan:
[1] HomePage
[1.1] Input a search query into the search bar to find specific products.
[1.2] Click the 'menu' button to explore the main navigation options.
[1.3] Click the 'OWASP Juice Shop' button to navigate to the main landing page.
[1.4] Click the 'Account' button to access account management options like login or registration.
[1.5] Click the 'EN' button to change the language of the website.
[1.6] Click on 'Apple Juice (1000ml)' to view its detailed product page.
[1.7] Click on 'Apple Pomace' to view its detailed product page.
[1.8] Click on 'Banana Juice (1000ml)' to view its detailed product page.
[1.9] Click on 'Best Juice Shop Salesman Artwork' to view its detailed product page.
[1.10] Click on 'Carrot Juice (1000ml)' to view its detailed product page.
[1.11] Click on 'Eggfruit Juice (500ml)' to view its detailed product page.
[1.12] Click on 'Fruit Press' to view its detailed product page.
[1.13] Click on 'Green Smoothie' to view its detailed product page.
[1.14] Click on 'Juice Shop "Permafrost" 2020 Edition' to view its detailed product page.

Now determine if the plan needs to be updated. This should happen in the following cases:
- the UI has changed between the previous and current webpage and some new interactive elements have been discovered that are not covered by the current plan

Here are some guidelines:
- try first determine which nested sub-level the current navigation is at
- then, if the plans need updating, use the tree indexing notation [a.b.c..] to find the parent_index to add the plans to

Now return your response as a list of plan items that will get added to the plan. 
This list should be empty if the plan does not need to be updated
        


Understand the content and provide
the parsed objects in json that match the following json_schema:


{
  "$defs": {
    "AddPlanItem": {
      "properties": {
        "description": {
          "title": "Description",
          "type": "string"
        },
        "parent_index": {
          "title": "Parent Index",
          "type": "string"
        }
      },
      "required": [
        "description",
        "parent_index"
      ],
      "title": "AddPlanItem",
      "type": "object"
    }
  },
  "properties": {
    "plan_items": {
      "items": {
        "$ref": "#/$defs/AddPlanItem"
      },
      "title": "Plan Items",
      "type": "array"
    }
  },
  "required": [
    "plan_items"
  ],
  "title": "AddPlanItemList",
  "type": "object"
}

Make sure to return an instance of the JSON, not the schema itself
"""

for i in range(5):
    # res = openai_41.invoke(MSG)
    # print(res)
    plan = UpdatePlanNested().invoke_with_msgs(
        model=gemini_25_flash,
        msgs=MSG
    )
    print(plan)


