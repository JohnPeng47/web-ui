"""
open_aikido_profile2.py

Launches a persistent Chrome context with an existing profile
and keeps the window open on https://app.aikido.dev.
"""

from playwright.sync_api import sync_playwright
import time
import signal
import sys
from pathlib import Path

PROFILE_DIR = Path(
    r"C:\Users\jpeng\AppData\Local\Google\Chrome\User Data\Profile 2"
)
TARGET_URL = "https://app.aikido.dev"


def main() -> None:
    if not PROFILE_DIR.exists():
        sys.exit(f"Profile path not found: {PROFILE_DIR}")

    with sync_playwright() as p:
        # Launch Chrome with the specified user profile
        context = p.chromium.launch_persistent_context(
            executable_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe",
            user_data_dir=str(PROFILE_DIR),
            channel="chrome",          # Requires `playwright install chrome`
            headless=False,
            args=["--start-maximized"],
        )

        page = context.new_page()
        res = page.goto(TARGET_URL, wait_until="load")
        print(res.text())
        print("Browser opened. Press Ctrl+C to close.")

        try:
            # Keep the process alive until SIGINT (Ctrl+C)
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            print("\nClosing browser ...")
        finally:
            context.close()


if __name__ == "__main__":
    main()
