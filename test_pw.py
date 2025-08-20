import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

PROFILE_DIR = Path(
    r"C:\Users\jpeng\AppData\Local\Google\Chrome\User Data\Profile 2"
)


async def download_html(url: str) -> str:
    """
    Download HTML content from a URL using Playwright
    
    Args:
        url (str): The URL to fetch HTML from
        
    Returns:
        str: The HTML content as a string
    """
    async with async_playwright() as p:
        # Launch browser (headless by default)
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe",
            headless=False
        )
        
        # Create a new page
        page = await browser.new_page()
        
        try:
            # Navigate to the URL
            await page.goto(url, wait_until='networkidle', timeout=20000)
            
            # Get the HTML content
            html_content = await page.content()
            
            return html_content
            
        except Exception as e:
            print(f"Error fetching HTML from {url}: {e}")
            return ""
            
        finally:
            # Clean up
            await browser.close()

async def main():
    """Example usage"""
    url = "http://147.79.78.153:3000"
    
    print(f"Downloading HTML from: {url}")
    html = await download_html(url)

    with open("login.html", "w") as f:
        f.write(html)

    if html:
        print(f"Successfully downloaded {len(html)} characters")
        print(f"First 200 characters:\n{html[:200]}...")
    else:
        print("Failed to download HTML")

# Synchronous wrapper function
def download_html_sync(url: str) -> str:
    """
    Synchronous wrapper for downloading HTML
    
    Args:
        url (str): The URL to fetch HTML from
        
    Returns:
        str: The HTML content as a string
    """
    return asyncio.run(download_html(url))

if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
    
    # Alternative synchronous usage
    # html_content = download_html_sync("https://example.com")
    # print(len(html_content))