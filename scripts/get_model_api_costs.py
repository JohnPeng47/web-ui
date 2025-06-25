import requests
import json

burp0_url = "https://raw.githubusercontent.com:443/BerriAI/litellm/main/model_prices_and_context_window.json"
burp0_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept": "*/*",
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://models.litellm.ai/",
    "Origin": "https://models.litellm.ai",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Priority": "u=4",
    "Te": "trailers",
    "Connection": "keep-alive"
}
res = requests.get(burp0_url, headers=burp0_headers)
with open("model_api_prices.json", "w", encoding="utf-8") as f:
    json.dump(res.json(), f, ensure_ascii=False, indent=2)
