import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
import difflib

DOM1 = """
Interactive Elements: |SCROLL|<mat-sidenav-content /> (0.5 pages above, 0.1 pages below)
\t[1]<div aria-label=Click for more information about the product />
\t\t[2]<img role=button alt=Apple Juice (1000ml) />
\t[3]<div aria-label=Click for more information about the product />
\t\t[4]<img role=button alt=Apple Pomace />
\t[5]<div aria-label=Click for more information about the product />
\t\t[6]<img role=button alt=Banana Juice (1000ml) />
\t[7]<div aria-label=Click for more information about the product />
\t\t[8]<img role=button alt=Best Juice Shop Salesman Artwork />
\t[9]<div aria-label=Click for more information about the product />
\t\t[10]<img role=button alt=Carrot Juice (1000ml) />
\t\t[11]<div />
\t\t\t[12]<div />
\t\t\t\tCarrot Juice (1000ml)
\t\t\t[13]<div />
\t\t\t\t[14]<span />
\t\t\t\t\t2.99¤
\t[15]<div aria-label=Click for more information about the product />
\t\t[16]<img role=button alt=Eggfruit Juice (500ml) />
\t\t[17]<div />
\t\t\t[18]<div />
\t\t\t\tEggfruit Juice (500ml)
\t\t\t[19]<div />
\t\t\t\t[20]<span />
\t\t\t\t\t8.99¤
\t[21]<div aria-label=Click for more information about the product />
\t\t[22]<img role=button alt=Fruit Press />
\t\t[23]<div />
\t\t\t[24]<div />
\t\t\t\tFruit Press
\t\t\t[25]<div />
\t\t\t\t[26]<span />
\t\t\t\t\t89.99¤
\t[27]<div aria-label=Click for more information about the product />
\t\t[28]<img role=button alt=Green Smoothie />
\t\t[29]<div />
\t\t\t[30]<div />
\t\t\t\tGreen Smoothie
\t\t\t[31]<div />
\t\t\t\t[32]<span />
\t\t\t\t\t1.99¤
\tOnly 1 left
\t[33]<div aria-label=Click for more information about the product />
\t\t[34]<img role=button alt=Juice Shop "Permafrost" 2020 Edition />
\t\t[35]<div />
\t\t\t[36]<div />
\t\t\t\tJuice Shop "Permafrost" 2020 Edition
\t\t\t[37]<div />
\t\t\t\t[38]<span />
\t\t\t\t\t9999.99¤
\t[39]<div aria-label=Click for more information about the product />
\t\t[40]<img role=button alt=Lemon Juice (500ml) />
\t\t[41]<div />
\t\t\t[42]<div />
\t\t\t\tLemon Juice (500ml)
\t\t\t[43]<div />
\t\t\t\t[44]<span />
\t\t\t\t\t2.99¤
\tOnly 3 left
\t[45]<div aria-label=Click for more information about the product />
\t\t[46]<img role=button alt=Melon Bike (Comeback-Product 2018 Edition) />
\t\t[47]<div />
\t\t\t[48]<div />
\t\t\t\tMelon Bike (Comeback-Product 2018 Edition)
\t\t\t[49]<div />
\t\t\t\t[50]<span />
\t\t\t\t\t2999¤
\tSold Out
\t[51]<div aria-label=Click for more information about the product />
\t\t[52]<img role=button alt=OWASP Juice Shop "King of the Hill" Facemask />
\t\t[53]<div />
\t\t\t[54]<div />
\t\t\t\tOWASP Juice Shop "King of the Hill" Facemask
\t\t\t[55]<div />
\t\t\t\t[56]<span />
\t\t\t\t\t13.49¤
"""

DOM2 = """
Interactive Elements: |SCROLL|<mat-sidenav-content /> (0.2 pages above, 0.4 pages below)
\t[1]<div aria-label=Click for more information about the product />
\t\t[2]<img role=button alt=Apple Juice (1000ml) />
\t\t[3]<div />
\t\t\t[4]<div />
\t\t\t\tApple Juice (1000ml)
\t\t\t[5]<div />
\t\t\t\t[6]<span />
\t\t\t\t\t1.99¤
\t[7]<div aria-label=Click for more information about the product />
\t\t[8]<img role=button alt=Apple Pomace />
\t\t[9]<div />
\t\t\t[10]<div />
\t\t\t\tApple Pomace
\t\t\t[11]<div />
\t\t\t\t[12]<span />
\t\t\t\t\t0.89¤
\t[13]<div aria-label=Click for more information about the product />
\t\t[14]<img role=button alt=Banana Juice (1000ml) />
\t\t[15]<div />
\t\t\t[16]<div />
\t\t\t\tBanana Juice (1000ml)
\t\t\t[17]<div />
\t\t\t\t[18]<span />
\t\t\t\t\t1.99¤
\tOnly 1 left
\t[19]<div aria-label=Click for more information about the product />
\t\t[20]<img role=button alt=Best Juice Shop Salesman Artwork />
\t\t[21]<div />
\t\t\t[22]<div />
\t\t\t\tBest Juice Shop Salesman Artwork
\t\t\t[23]<div />
\t\t\t\t[24]<span />
\t\t\t\t\t5000¤
\t[25]<div aria-label=Click for more information about the product />
\t\t[26]<img role=button alt=Carrot Juice (1000ml) />
\t\t[27]<div />
\t\t\t[28]<div />
\t\t\t\tCarrot Juice (1000ml)
\t\t\t[29]<div />
\t\t\t\t[30]<span />
\t\t\t\t\t2.99¤
\t[31]<div aria-label=Click for more information about the product />
\t\t[32]<img role=button alt=Eggfruit Juice (500ml) />
\t\t[33]<div />
\t\t\t[34]<div />
\t\t\t\tEggfruit Juice (500ml)
\t\t\t[35]<div />
\t\t\t\t[36]<span />
\t\t\t\t\t8.99¤
\t[37]<div aria-label=Click for more information about the product />
\t\t[38]<img role=button alt=Fruit Press />
\t\t[39]<div />
\t\t\t[40]<div />
\t\t\t\tFruit Press
\t\t\t[41]<div />
\t\t\t\t[42]<span />
\t\t\t\t\t89.99¤
\t[43]<div aria-label=Click for more information about the product />
\t\t[44]<img role=button alt=Green Smoothie />
\t\t[45]<div />
\t\t\t[46]<div />
\t\t\t\tGreen Smoothie
\t\t\t[47]<div />
\t\t\t\t[48]<span />
\t\t\t\t\t1.99¤
\tOnly 1 left
\t[49]<div aria-label=Click for more information about the product />
\t\t[50]<img role=button alt=Juice Shop "Permafrost" 2020 Edition />
\t\t[51]<div />
\t\t\t[52]<div />
\t\t\t\tJuice Shop "Permafrost" 2020 Edition
\t[53]<div aria-label=Click for more information about the product />
\t\t[54]<img role=button alt=Lemon Juice (500ml) />
\t\t[55]<div />
\t\t\t[56]<div />
\t\t\t\tLemon Juice (500ml)
\tOnly 3 left
\t[57]<div aria-label=Click for more information about the product />
\t\t[58]<img role=button alt=Melon Bike (Comeback-Product 2018 Edition) />
\t\t[59]<div />
\t\t\t[60]<div />
\t\t\t\tMelon Bike (Comeback-Product 2018 Edition)
\tSold Out
\t[61]<div aria-label=Click for more information about the product />
\t\t[62]<img role=button alt=OWASP Juice Shop "King of the Hill" Facemask />
\t\t[63]<div />
\t\t\t[64]<div />
\t\t\t\tOWASP Juice Shop "King of the Hill" Facemask
[65]<mat-dialog-container role=dialog />
\tApple Juice (1000ml)
\tThe all-time classic.
\t[66]<p />
\t\t1.99¤
\t[67]<mat-divider role=separator />
\t[68]<button />
\t[69]<mat-expansion-panel-header role=button />
\t\t[70]<span />
\t\t\t[71]<mat-panel-title />
\t\t\t\t[72]<span />
\t\t\t\t\tReviews
\t\t\t\t[73]<span />
\t\t\t\t\t(1)
\t\t[74]<span />
\t[75]<mat-divider role=separator />
\t[76]<button aria-label=Close Dialog type=button />
\t\tclose
\t\tClose
"""

PROMPT = """
You are given two DOM trees 
"""