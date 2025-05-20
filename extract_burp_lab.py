import asyncio
from playwright.async_api import async_playwright

URL = "https://portswigger.net/web-security/sql-injection/examining-the-database/lab-listing-database-contents-oracle"

async def extract_text_from_div(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url)

        # Wait for the specific div to be present
        await page.wait_for_selector("div.section.theme-white")

        # Extract all text content under the div
        # This uses a locator and then extracts all inner text from all matching elements
        # and joins them. If there's only one such div, it will get its content.
        # If there are multiple, it will concatenate their content.
        div_locator = page.locator("div.section.theme-white")
        
        # Get all text nodes within the div, including those in nested elements
        all_text_content = await div_locator.evaluate_all("""
            elements => elements.map(el => {
                let text = '';
                const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
                let node;
                while(node = walker.nextNode()) {
                    text += node.textContent.trim() + ' ';
                }
                return text.trim();
            }).join('\\n\\n')
        """)
        
        print("Extracted Text:")
        print(all_text_content)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(extract_text_from_div(URL))