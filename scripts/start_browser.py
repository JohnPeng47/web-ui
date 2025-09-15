from cnc.workers.agent.browser import start_single_browser
import asyncio

import asyncio
import logging
import os
import psutil
import aiohttp
from pathlib import Path
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Your constants - replace with your actual values
BROWSER_PROFILE_DIR = Path("./browser_profile")  # Replace with your actual path
BROWSER_CDP_PORT = 9222  # Replace with your actual port
BROWSER_PROXY_HOST = "127.0.0.1"  # Replace with your actual proxy host
BROWSER_PROXY_PORT = 8080  # Replace with your actual proxy port

def check_permissions(path):
    """Check if the browser executable exists and has proper permissions"""
    try:
        if os.path.exists(path):
            file_stats = os.stat(path)
            print(f"✓ File exists: {path}")
            print(f"✓ File size: {file_stats.st_size:,} bytes")
            print(f"✓ Permissions: {oct(file_stats.st_mode)}")
            return True
        else:
            print(f"✗ File does not exist: {path}")
            return False
    except Exception as e:
        print(f"✗ Error checking file: {e}")
        return False

def check_profile_in_use(profile_dir):
    """Check if any Chrome/Chromium processes are using this profile"""
    print(f"Checking if profile is in use: {profile_dir}")
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if str(profile_dir) in cmdline:
                        print(f"⚠️  Found process using profile: PID {proc.info['pid']} - {proc.info['name']}")
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        print("✓ No processes found using the profile")
        return False
    except Exception as e:
        print(f"Error checking processes: {e}")
        return False

def is_port_in_use(port):
    """Check if a port is already in use"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

async def test_proxy():
    """Test if the proxy server is responding"""
    try:
        print(f"Testing proxy connection: {BROWSER_PROXY_HOST}:{BROWSER_PROXY_PORT}")
        async with aiohttp.ClientSession() as session:
            proxy_url = f"http://{BROWSER_PROXY_HOST}:{BROWSER_PROXY_PORT}"
            async with session.get("http://httpbin.org/ip", proxy=proxy_url, timeout=10) as response:
                result = await response.text()
                print(f"✓ Proxy test successful: {result[:100]}...")
                return True
    except Exception as e:
        print(f"⚠️  Proxy test failed: {e}")
        return False

async def test_minimal_browser():
    """Test if Playwright can launch a basic browser"""
    try:
        print("Testing minimal browser launch...")
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=False, timeout=30000)
        page = await browser.new_page()
        await page.goto("https://example.com")
        title = await page.title()
        print(f"✓ Minimal browser test successful - Page title: {title}")
        await browser.close()
        await pw.stop()
        return True
    except Exception as e:
        print(f"✗ Minimal browser test failed: {e}")
        return False

# async def start_single_browser():
#     """Main function to start the browser with debugging"""    
#     # Pre-flight checks
#     executable_path = r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
    
#     pw = None
#     browser = None
    
#     try:
#         print("Step 6.1: Starting playwright...")
#         pw = await async_playwright().start()
#         print("✓ Playwright started successfully")
        
#         print("Step 6.2: Browser configuration:")
#         print(f"  - user_data_dir: {BROWSER_PROFILE_DIR}")
#         print(f"  - CDP port: {BROWSER_CDP_PORT}")
#         print(f"  - Proxy: {BROWSER_PROXY_HOST}:{BROWSER_PROXY_PORT}")
#         print(f"  - Executable: {executable_path}")
#         print(f"  - Headless: True")
        
#         print("Step 6.3: Launching persistent context...")
        
#         # Try with minimal args first if proxy failed
#         args = [
#             f"--remote-debugging-port={BROWSER_CDP_PORT}", 
#             "--remote-debugging-address=127.0.0.1",
#         ]
        
#         if proxy_ok:
#             args.append(f"--proxy-server=http://{BROWSER_PROXY_HOST}:{BROWSER_PROXY_PORT}")
#         else:
#             print("⚠️  Skipping proxy due to connection issues")
        
#         # Add stability args
#         args.extend([
#             "--no-sandbox",
#             "--disable-dev-shm-usage",
#             "--disable-gpu",
#             "--disable-web-security",
#             "--disable-features=VizDisplayCompositor"
#         ])
        
#         browser = await pw.chromium.launch_persistent_context(
#             user_data_dir=str(BROWSER_PROFILE_DIR),
#             headless=False,
#             executable_path=executable_path,
#             timeout=60000,  # 60 seconds
#             args=args,
#         )
        
#         print("✓ Browser launched successfully!")
        
#         # Test browser responsiveness
#         print("Step 6.4: Testing browser responsiveness...")
#         page = await browser.new_page()
#         await page.goto("about:blank")
#         print("✓ Browser is responsive")
#         await page.close()
        
#         print("Step 6.5: Browser is ready and running...")
#         print("Press Ctrl+C to stop")
        
#         # Keep browser running until interrupted
#         while True:
#             await asyncio.sleep(1)
            
#     except KeyboardInterrupt:
#         print("\n🛑 Browser shutdown requested")
#     except asyncio.TimeoutError:
#         print("\n❌ Browser launch timed out!")
#     except Exception as e:
#         print(f"\n❌ Browser error: {e}")
#         import traceback
#         traceback.print_exc()
#     finally:
#         print("\nCleaning up...")
#         if browser:
#             try:
#                 await browser.close()
#                 print("✓ Browser closed")
#             except Exception as e:
#                 print(f"⚠️  Error closing browser: {e}")
        
#         if pw:
#             try:
#                 await pw.stop()
#                 print("✓ Playwright stopped")
#             except Exception as e:
#                 print(f"⚠️  Error stopping playwright: {e}")
        
#         print("Done!")

if __name__ == "__main__":
    # Make sure to install required packages:
    # pip install playwright aiohttp psutil
    asyncio.run(start_single_browser())