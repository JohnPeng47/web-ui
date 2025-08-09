from src.agent.discovery import CheckPlanCompletion
from src.llm_models import openai_4o, cohere_command_a, openai_41

MSGS = """
Here is a plan used by an agent to map out all the interactive components of a webpage:
[ ] 1. Click on the 'OWASP Juice Shop' button to navigate to the main shop page or home page.
[ ] 2. Click on the 'account_circle Account' button to access user account settings, login, or registration.
[ ] 3. Click on the 'language EN' button to change the language of the webpage.
[ ] 4. Click on the 'menu' button to open the navigation menu and explore different sections of the shop.
[ ] 5. Interact with the 'search' field to search for specific products or categories.
[ ] 6. Click on the 'Apple Juice (1000ml)' image or title to view product details, reviews, or add to cart.
[ ] 7. Click on the 'Apple Pomace' image or title to view product details, reviews, or add to cart.
[ ] 8. Click on the 'Banana Juice (1000ml)' image or title to view product details, reviews, or add to cart. Note the 'Only 1 left' label for urgency.
[ ] 9. Click on the 'Best Juice Shop Salesman Artwork' image or title to view product details, reviews, or add to cart.
[ ] 10. Click on the 'Carrot Juice (1000ml)' image or title to view product details, reviews, or add to cart.
[ ] 11. Click on the 'Eggfruit Juice (500ml)' image or title to view product details, reviews, or add to cart.
[ ] 12. Click on the 'Fruit Press' image or title to view product details, reviews, or add to cart.
[ ] 13. Click on the 'Green Smoothie' image or title to view product details, reviews, or add to cart. Note the 'Only 1 left' label for urgency.
[ ] 14. Click on the 'Juice Shop "Permafrost" 2020 Edition' image or title to view product details, reviews, or add to cart.

Here is the current webpage:
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

Here is the previous goal that resulted in a transition to the current webpage:
Begin executing the plan to interact with the webpage exhaustively, starting with the first action: clicking on the 'OWASP Juice Shop' button.

Now try to determine which plan items have been completed by the agent
        


Understand the content and provide
the parsed objects in json that match the following json_schema:


{
  "properties": {
    "completed_plans": {
      "items": {
        "type": "integer"
      },
      "title": "Completed Plans",
      "type": "array"
    }
  },
  "required": [
    "completed_plans"
  ],
  "title": "CompletedPlans",
  "type": "object"
}

Make sure to return an instance of the JSON, not the schema itself

"""
for i in range(10):
    plan = CheckPlanCompletion().invoke_with_msgs(
        model=cohere_command_a,
        msgs=MSGS
    )
    print(plan)
