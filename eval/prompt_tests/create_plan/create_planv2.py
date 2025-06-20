from src.agent.discovery import CreatePlanNested
from src.llm_models import deepseek_r1

MSG = """
You are tasked with creating a plan for navigating a webpage. The plan should be exhaustive in
covering steps for every
possible interaction with the current webpage. Here is the current webpage:
This website uses fruit cookies to ensure you get the juiciest tracking experience.
[0]<a But me wait!/>
[1]<a Me want it!/>
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
Juice Shop "Permafrost" 2020 Edition
9999.99¤
[2]<img />
Lemon Juice (500ml)
2.99¤
Only 3 left
[3]<img />
Melon Bike (Comeback-Product 2018 Edition)
2999¤
Sold Out
[4]<img />
OWASP Juice Shop "King of the Hill" Facemask
13.49¤
Items per page:
[5]<mat-select 12/>
1 – 12 of 36
[6]<button />
[7]<button />
Language has been changed to English
Force page reload
[8]<div />
Welcome to OWASP Juice Shop!
Being a web application with a vast number of intended security vulnerabilities, the
OWASP Juice Shop
is supposed to be the opposite of a best practice or template application for web developers: It is
an awareness, training, demonstration and exercise tool for security risks in modern web
applications. The
OWASP Juice Shop
is an open-source project hosted by the non-profit
Open Worldwide Application Security Project (OWASP)
and is developed and maintained by volunteers. Check out the link below for more information and
documentation on the project.
[9]<a https://owasp-juice.shop/>
[10]<button school
Help getting started/>
[11]<button visibility_off
Dismiss/>
[12]<div />
Your output should be a list of plans under a two-tier hierarchy.
At the first level (UIGroup), you should decompose the page into non-overlapping UI hierarchies,
each of which captures a set of interactive elements
At the second level, these are the set of actions to be performed on the UI hierarchy
Here are some things to watch for when creating the plan:
- always refer to interactive elements by their name / description rather than by their numeric
label
- UIGroups that are more likely to lead to new functionalities should be ranked higher in the list
Now generate your plan
Understand the content and provide
the parsed objects in json that match the following json_schema:
{
  "$defs": {
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
    },
    "UIGroup": {
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "items": {
          "items": {
            "$ref": "#/$defs/PlanItem"
          },
          "title": "Items",
          "type": "array"
        }
      },
      "required": [
        "name",
        "items"
      ],
      "title": "UIGroup",
      "type": "object"
    }
  },
  "properties": {
    "ui_groups": {
      "items": {
        "$ref": "#/$defs/UIGroup"
      },
      "title": "Ui Groups",
      "type": "array"
    }
  },
  "required": [
    "ui_groups"
  ],
  "title": "Plan",
  "type": "object"
}
Make sure to return an instance of the JSON, not the schema itself
"""

plan = CreatePlanNested().invoke_with_msgs(
    model=deepseek_r1,
    msgs=MSG
)
print(plan)


