import asyncio

from src.agent.discovery.sites.base import start_discovery_agent

AUTH_COOKIES = [
    {
        "domain": ".aikido.dev",
        "expirationDate": 1760975307,
        "hostOnly": False,
        "httpOnly": False,
        "name": "intercom-session-j0dzii6j",
        "path": "/",
        "sameSite": "lax",
        "secure": False,
        "session": False,
        "storeId": None,
        "value": "elhpRStZY2QxaXBZbGlpOGxEV2V5T3FnUkxFa0xKaHRpdDZVTjV5QkdQc0tKanJEZml6V2NwcE9iRmpVSzhmUnYreW8rMFZYOVdGOFlrY1BSYUVHWFpzczQ3R3hmaGh1dExoZDlHR0RGcUk9LS1QTzAxcitaa3prdUViYWVBQXp2dENBPT0=--2d1b65c7d14860190ced47e9cbbe269a75de8e6e"
    },
    {
        "domain": ".aikido.dev",
        "expirationDate": 1783700507,
        "hostOnly": False,
        "httpOnly": False,
        "name": "intercom-device-id-j0dzii6j",
        "path": "/",
        "sameSite": "lax",
        "secure": False,
        "session": False,
        "storeId": None,
        "value": "5b699cd2-65d8-432b-bdaf-d47b12cad300"
    },
    {
        "domain": "app.aikido.dev",
        "expirationDate": 1760439525.657082,
        "hostOnly": True,
        "httpOnly": True,
        "name": "auth",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJhaWtpZG8uZGV2IiwiYXVkIjoidXNlcnMuYWlraWRvIiwiaWF0IjoxNzYwMzY3NTI1LCJuYmYiOjE3NjAzNjc1MTUsImV4cCI6MTc2MDQzOTUyNSwidXNlcl9pZCI6NDIwNTV9.nkSrfrjwCdLTMjocGSpwpPk-yiGCfnenwwPa7av8Da4"
    },
    {
        "domain": "app.aikido.dev",
        "hostOnly": True,
        "httpOnly": False,
        "name": "locale",
        "path": "/",
        "sameSite": None,
        "secure": False,
        "session": True,
        "storeId": None,
        "value": "en"
    }
]

async def main():
    START_URLS = [
        "https://app.aikido.dev/settings/integrations/repositories"
    ]
    SCOPES = [
        # "https://app.aikido.dev"
    ]
    INIT_TASK = """
After visiting https://app.aikido.dev/settings/integrations/repositories immediately exit
"""
    await start_discovery_agent(
        START_URLS, 
        SCOPES, 
        init_task=INIT_TASK, 
        challenge_client=None, 
        auth_cookies=AUTH_COOKIES
    )

if __name__ == "__main__":
    asyncio.run(main())