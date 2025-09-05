import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

from common.constants import (
    BROWSER_PROFILE_DIR, 
    BROWSER_CDP_PORT 
)
from playwright.async_api import async_playwright
from browser_use.browser import BrowserSession, BrowserProfile

async def start_single_browser():
    print("Starting single browser")
    pw = None
    browser = None
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=True,
            executable_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe",
            args=[f"--remote-debugging-port={BROWSER_CDP_PORT}", "--remote-debugging-address=127.0.0.1"],
        )        
        # idk why but need this here or CDP doesn't work
        browser_session = BrowserSession(
            browser_profile=BrowserProfile(
                keep_alive=True,
            ),
            is_local=False,
            cdp_url=f"http://127.0.0.1:{BROWSER_CDP_PORT}/",
        )
        await browser_session.start()

        # Keep browser running until interrupted
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("Browser shutdown requested")
    except Exception as e:
        print(f"Browser error: {e}")
    finally:
        if browser:
            try:
                await browser.close()
                print("Browser closed")
            except Exception as e:
                print(f"Error closing browser: {e}")
        
        if pw:
            try:
                await pw.stop()
                print("Playwright stopped")
            except Exception as e:
                print(f"Error stopping playwright: {e}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def get_browser_session():
    browser_session = BrowserSession(
        browser_profile=BrowserProfile(
            keep_alive=True,
        ),
        is_local=False,
        cdp_url=f"http://127.0.0.1:{BROWSER_CDP_PORT}/",
    )
    await browser_session.start()
    return browser_session