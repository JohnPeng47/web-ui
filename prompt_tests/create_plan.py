from src.llm_models import openai_o3
from src.agent.discovery import CreatePlanNested

PROMPT = """
You are tasked with creating a plan for triggering all meaningful DOM interaction on the webpage except for navigational actions. Meaningful actions are actions that change the application functional state, rather than purely cosmetic changes.

Here is the current webpage:
|SCROLL|<mat-sidenav-content /> (0.0 pages above, 0.6 pages below)
	[1]<button aria-label=Open Sidenav />
		menu
	[2]<button aria-label=Back to homepage />
		OWASP Juice Shop
	[3]<div />
	[4]<app-mat-search-bar aria-label=Click to search />
		[5]<mat-form-field />
		[6]<span />
			[7]<mat-icon role=img />
				search
	[8]<button aria-label=Show/hide account menu />
		account_circle
		Account
	[9]<button aria-label=Language selection menu />
		language
		EN
	All Products
	[10]<div />
	[11]<div aria-label=Click for more information about the product />
		[12]<img role=button alt=Apple Juice (1000ml) />
		[13]<div />
			[14]<div />
				Apple Juice (1000ml)
			[15]<div />
				[16]<span />
					1.99¤
	[17]<div aria-label=Click for more information about the product />
		[18]<img role=button alt=Apple Pomace />
		[19]<div />
			[20]<div />
				Apple Pomace
			[21]<div />
				[22]<span />
					0.89¤
	[23]<div aria-label=Click for more information about the product />
		[24]<img role=button alt=Banana Juice (1000ml) />
		[25]<div />
			[26]<div />
				Banana Juice (1000ml)
			[27]<div />
				[28]<span />
					1.99¤
	Only 1 left
	[29]<div aria-label=Click for more information about the product />
		[30]<img role=button alt=Best Juice Shop Salesman Artwork />
		[31]<div />
			[32]<div />
				Best Juice Shop Salesman Artwork
			[33]<div />
				[34]<span />
					5000¤
	[35]<div aria-label=Click for more information about the product />
		[36]<img role=button alt=Carrot Juice (1000ml) />
		[37]<div />
			[38]<div />
				Carrot Juice (1000ml)
			[39]<div />
				[40]<span />
					2.99¤
	[41]<div aria-label=Click for more information about the product />
		[42]<img role=button alt=Eggfruit Juice (500ml) />
		[43]<div />
			[44]<div />
				Eggfruit Juice (500ml)
			[45]<div />
				[46]<span />
					8.99¤
	[47]<div aria-label=Click for more information about the product />
		[48]<img role=button alt=Fruit Press />
		[49]<div />
			[50]<div />
				Fruit Press
			[51]<div />
				[52]<span />
					89.99¤
	[53]<div aria-label=Click for more information about the product />
		[54]<img role=button alt=Green Smoothie />
		[55]<div />
			[56]<div />
				Green Smoothie
			[57]<div />
				[58]<span />
					1.99¤

IMPORTANT: Do not create plans which might trigger a navigational action resulting in the browser going to another page ie. clicking on a button that you think will cause a navigation action to occur 

Guidelines for writing the plan:
- Focus on describing the overall goal of the plan rather than specific step
- Focus on interacting with DOM elements *only* and *not* responsive interactions like screen resizing, voice-over screen reader, etc.
- Refer to interactive elements by their visible label, not a numeric index.
- List higher-leverage interactions earlier
- If there are repeated elements on a page select a representative sample to include rather than all of them

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
for i in range(3):
  for plan in res.plan_descriptions:
      print(plan)
