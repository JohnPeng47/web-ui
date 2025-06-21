from src.agent.discovery import UpdatePlan
from src.llm_models import openai_4o, cohere_command_a, openai_41

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

Here is the previous plan:
[ ] 1. Click on 'menu' button to explore more navigation options.
[ ] 2. Click on 'OWASP Juice Shop' button to navigate to the homepage.
[ ] 3. Click on 'Account' button to view account details or login.
[ * ] 4. Click on 'language (EN)' button to change the language.
[ ] 5. Interact with the search bar to find specific products.
[ ] 6. Review each product image and price: 'Apple Juice (1000ml)', 'Apple Pomace', 'Banana Juice (1000ml)', etc.
[ ] 7. Select 'Items per page' dropdown to change the number of products displayed per page.
[ ] 8. Navigate through products using pagination buttons.    

Now determine if the plan needs to be updated. This should happen in the following cases:
- the UI has changed between the previous and current webpage and some new interactive elements have been discovered that are not covered by the current plan

Now return your response as a list of plan items that will get added to the plan. 
This list should be empty if the plan does not need to be updated

Understand the content and provide
the parsed objects in json that match the following json_schema:

{
  "$defs": {
    "AddPlanItem": {
      "properties": {
        "plan_item": {
          "$ref": "#/$defs/PlanItem"
        },
        "index": {
          "title": "Index",
          "type": "integer"
        }
      },
      "required": [
        "plan_item",
        "index"
      ],
      "title": "AddPlanItem",
      "type": "object"
    },
    "PlanItem": {
      "properties": {
        "description": {
          "title": "Description",
          "type": "string"
        },
        "completed": {
          "default": false,
          "title": "Completed",
          "type": "boolean"
        }
      },
      "required": [
        "description"
      ],
      "title": "PlanItem",
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
    plan = UpdatePlan().invoke_with_msgs(
        model=cohere_command_a,
        msgs=MSG
    )
    print(plan)




