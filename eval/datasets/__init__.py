from pydantic import BaseModel

from .discovery.juiceshop import JUICE_SHOP_ALL as JUICE_SHOP_ALL_DISCOVERY
from .discovery.juiceshop_exploit import JUICE_SHOP_VULNERABILITIES as JUICE_SHOP_ALL_EXPLOIT

# class Challenge 

# JUICE_SHOP_BASE_URL = "http://147.79.78.153:3000"
# JUICE_SHOP_ALL = {**JUICE_SHOP_ALL_DISCOVERY, **JUICE_SHOP_VULNERABILITIES}
# JUICE_SHOP_SUBSET = {p: JUICE_SHOP_ALL.get(p, []) for p in TEST_PATHS if p}
