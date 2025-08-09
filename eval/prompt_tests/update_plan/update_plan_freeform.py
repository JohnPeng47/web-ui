from src.agent.discovery import UpdatePlanNested
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
[1.1] Click on the 'menu' button to open the navigation menu and explore available options.
[1.2] Click on the 'OWASP Juice Shop' button to navigate to the homepage or main landing page.
[1.3] Click on the 'account_circle Account' button to access user account settings, login, or registration.
[1.4] Click on the 'language EN' button to change the language of the webpage.
[1.5] Click on any product image (e.g., Apple Juice, Fruit Press) to view detailed product information.
[1.6] Click on the 'search' field to enter a search query and find specific products or content.
[1.7] Interact with products displaying 'Only 1 left' (e.g., Banana Juice, Green Smoothie) to add them to the cart before they run out.
[1.8] Click on the 'Best Juice Shop Salesman Artwork' to view or purchase the artwork.
[1.9] Scroll through the 'All Products' section to browse available items and their prices.
[1.10] Interact with high-value items (e.g., 'Juice Shop "Permafrost" 2020 Edition') to view details or add to cart.

Come up with:
1. The plan index to which to add the subplans
2. The plans to add
"""

for i in range(5):
    res = cohere_command_a.invoke(MSG)
    print(res.content)
    # plan = UpdatePlanNested().invoke_with_msgs(
    #     model=openai_41,
    #     msgs=MSG
    # )
    # print(plan)




