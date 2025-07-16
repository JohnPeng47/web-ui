from pentest_bot.web_exploit.base_agent import LaunchPentestBots, LabInfo
from typing import Callable, Dict
from playwright.sync_api import sync_playwright


CHROME_EXE_PATH = r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
CHROME_PROFILE_PATH = r"C:\Users\jpeng\AppData\Local\Google\Chrome\User Data\Default"

class DiscoveryLabInfo(LabInfo):
    pass


def launch_pw_context():
    with sync_playwright() as p:
        pw_context = p.chromium.launch(
            executable_path=CHROME_EXE_PATH,
        )
        context = pw_context.new_context()
        return context

if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor
    import threading
    
    def test_thread(thread_id):
        print(f"Thread {thread_id} starting...")
        try:
            pw_context = launch_pw_context()
            print(f"Thread {thread_id} successfully launched context: {pw_context}")
            # Keep context alive briefly for testing
            import time
            time.sleep(2)
            pw_context.close()
            print(f"Thread {thread_id} closed context")
        except Exception as e:
            print(f"Thread {thread_id} failed: {e}")
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(test_thread, i) for i in range(3)]
        for future in futures:
            future.result()