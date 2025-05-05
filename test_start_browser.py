from browser_use.browser.browser import Browser, BrowserConfig
import asyncio

async def main():
    # Default configuration (headless=False, disable_security=True)
    browser_instance = Browser()

    # Or with custom configuration
    config = BrowserConfig(
        headless=False,
        # Add other configuration options here as needed
        # e.g., proxy_server="http://yourproxy:port"
    )
    browser_instance_custom = Browser(config=config)

    # You usually need to initialize it to get the actual playwright browser
    # This happens implicitly when you create a context, or you can call it directly
    playwright_browser = await browser_instance.get_playwright_browser()
    print("Playwright browser started:", playwright_browser)

    # Remember to close the browser when done
    # await browser_instance.close()
    # await browser_instance_custom.close() # If you created the custom one

if __name__ == "__main__":
    asyncio.run(main())
