from src.agent.discovery import CheckPlanCompletion
from src.llm_models import openai_4o, cohere_command_a, openai_41

MSG = """
Here is a plan used by an agent to map out all the interactive components of a webpage:
[ ] 1. Click on the 'OWASP Juice Shop' button to navigate to the main page or a specific section of the shop.
[ ] 2. Interact with the 'menu' button to open the navigation menu and explore different categories or sections of the website.
[ * ] 3. Click on the 'account_circle' button to access user account settings, login, or registration options.
[ ] 4. Use the 'language' button to change the website's language to a preferred option other than English.
[ ] 5. Click on any product image (e.g., Apple Juice, Banana Juice) to view detailed product information, reviews, or add the item to the cart.
[ ] 6. Interact with the 'Items per page' dropdown (currently set to 12) to change the number of products displayed per page for better browsing.
[ ] 7. Click on the next page button (button [18]) to navigate to the next set of products if there are more than 12 items available.
[ ] 8. Use the search bar to search for specific products or keywords to quickly find relevant items.
[ ] 9. Click on products with limited stock (e.g., Banana Juice, Green Smoothie) to ensure availability and potentially add them to the cart before they run out.
[ ] 10. Explore the 'Sold Out' product (Melon Bike) to understand if it can be back-ordered or to view similar products.
[ ] 11. Click on the high-value or unique items (e.g., Best Juice Shop Salesman Artwork, Juice Shop 'Permafrost' 2020 Edition) to view details or add them to the cart.
[ ] 12. Interact with the previous page button (button [19]) if available, to navigate back to the previous set of products.

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

Here is the previous goal that resulted in a transition to the current webpage:
Execute the next action in the plan: Interact with the 'menu' button to open the navigation menu and explore different categories or sections of the website.

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
        model=openai_41,
        msgs=MSG
    )
    print(plan)
