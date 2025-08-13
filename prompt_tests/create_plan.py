from src.llm_models import openai_o3
from src.agent.discovery import CreatePlanNested

PROMPT = """
[CreatePlanNested]: 
You are tasked with creating a plan for navigating a webpage. 
The plan should be exhaustive in covering steps for every possible interaction with the current webpage *except* for navigational actions. 
Here is the current webpage:
This website uses fruit cookies to ensure you get the juiciest tracking experience.
[0]<a button;learn more about cookies>But me wait!/>
[1]<a button;dismiss cookie message>Me want it!/>
[2]<button Open Sidenav>menu/>
[3]<button Back to homepage>OWASP Juice Shop/>
[4]<img />
search
[5]<button Show/hide account menu>account_circle
Account/>
[6]<button Show the shopping cart>shopping_cart
Your Basket
0/>
[7]<button Language selection menu>language
EN/>
All Products
[8]<img Apple Juice (1000ml);button/>
Apple Juice (1000ml)
1.99¤
[9]<button Add to Basket/>
[10]<img Apple Pomace;button/>
Apple Pomace
0.89¤
[11]<button Add to Basket/>
[12]<img Banana Juice (1000ml);button/>
Banana Juice (1000ml)
1.99¤
[13]<button Add to Basket/>
Only 1 left
[14]<img Best Juice Shop Salesman Artwork;button/>
Best Juice Shop Salesman Artwork
5000¤
[15]<button Add to Basket/>
[16]<img Carrot Juice (1000ml);button/>
Carrot Juice (1000ml)
2.99¤
[17]<button Add to Basket/>
Eggfruit Juice (500ml)
8.99¤
[18]<button Add to Basket/>
[19]<img Fruit Press;button/>
Fruit Press
89.99¤
[20]<button Add to Basket/>
[21]<img button;Green Smoothie/>
Green Smoothie
1.99¤
[22]<button Add to Basket/>
Only 1 left
[23]<img Juice Shop "Permafrost" 2020 Edition;button/>
Juice Shop "Permafrost" 2020 Edition
9999.99¤
[24]<button Add to Basket/>

Guidelines for writing the plan:
- Refer to interactive elements by their visible label, not a numeric index.
- List higher-leverage interactions earlier

IMPORTANT: ignore all interactions which might trigger a navigational action resulting in the browser going to another page

Return JSON that conforms to the Plan schema.

Understand the content and provide the parsed objects in json that match the following json_schema:

{
  "properties": {
    "plan_descriptions": {
      "items": {
        "type": "string"
      },
      "title": "Plan Descriptions",
      "type": "array"
    }
  },
  "required": [
    "plan_descriptions"
  ],
  "title": "InitialPlan",
  "type": "object"
}

Make sure to return an instance of the JSON, not the schema itself
"""

model = openai_o3()
res = CreatePlanNested().invoke_with_msgs(model, [PROMPT])
for plan in res.plan_descriptions:
    print(plan)
