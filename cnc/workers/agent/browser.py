import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
import time

from common.constants import (
    BROWSER_PROFILE_DIR_2,
    BROWSER_CDP_PORT,
    BROWSER_PROXY_HOST,
    BROWSER_PROXY_PORT,
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
            user_data_dir=str(BROWSER_PROFILE_DIR_2),
            headless=True,
            executable_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe",
            args=[
                "--ignore-certificate-errors",
                "--ignore-ssl-errors",
                "--ignore-certificate-errors-spki-list",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                f"--remote-debugging-port={BROWSER_CDP_PORT}", 
                "--remote-debugging-address=127.0.0.1",
                f"--proxy-server=http://{BROWSER_PROXY_HOST}:{BROWSER_PROXY_PORT}"
            ],
        )        
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

async def get_browser_session(sleep_time=10):
    """Get a browser session from browser-use"""
    retry_count = 3
    browser_session = None
    
    for attempt in range(retry_count):
        try:
            # Create a fresh BrowserSession for each attempt
            browser_session = BrowserSession(
                browser_profile=BrowserProfile(
                    keep_alive=True,
                ),
                is_local=False,
                cdp_url=f"http://127.0.0.1:{BROWSER_CDP_PORT}/",
            )
            
            # Start the browser session
            await browser_session.start()
            
            # Verify the browser is actually connected
            if browser_session._cdp_client_root is None:
                raise Exception("CDP client not initialized")
            
            if browser_session.agent_focus is None:
                raise Exception("No agent focus established")
            
            # Test that the browser is responsive
            test_result = await browser_session.agent_focus.cdp_client.send.Runtime.evaluate(
                params={'expression': '1 + 1', 'returnByValue': True},
                session_id=browser_session.agent_focus.session_id
            )
            
            if test_result.get('result', {}).get('value') != 2:
                raise Exception("Browser not responsive")
            
            print(f"Browser session established successfully on attempt {attempt + 1}")
            return browser_session
            
        except Exception as e:
            print(f"Browser session attempt {attempt + 1} failed: {e}")
            
            # Clean up the failed session
            if browser_session:
                try:
                    await browser_session.kill()
                except:
                    pass  # Ignore cleanup errors
                browser_session = None  # Clear the reference
            
            if attempt < retry_count - 1:
                print(f"Sleeping before retry...")
                await asyncio.sleep(sleep_time)
            else:
                raise Exception(f"Browser session failed after {retry_count} attempts")

if __name__ == "__main__":
    asyncio.run(get_browser_session())