#!/usr/bin/env python3
"""
HackerOne Report URL Scraper

This script uses the custom Browser class to fetch HackerOne Hacktivity page,
find all report URLs using regex, and print them.
"""
import asyncio
import re
import logging
import time
import random
import json
from datetime import datetime
from browser_use.browser.browser import Browser, BrowserConfig
from pydantic import BaseModel, Field
from typing import Dict, List, Tuple

# Configure root logger first
logging.basicConfig(
    level=logging.INFO,
)

# Configure file handler
file_handler = logging.FileHandler("scrape.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

# Configure console handler 
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

# Get the root logger and add the handlers
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Get the module logger
logger = logging.getLogger(__name__)

OUT_DIR = "scrapers/reports"
REPORT_PAGE = "https://hackerone.com/hacktivity/overview?queryString=disclosed%3Atrue&sortField=latest_disclosable_activity_at&sortDirection=DESC&pageIndex={index}"
REPORT_TIMEOUT = 15000

class ReportContent(BaseModel):
    reported_to: str
    reported_by: str
    title: str
    content: str | None = None
    severity: Tuple[float, float | None] | None = None
    bounty: float | None = None
    weaknesses: List[str] = Field(default_factory=list)
    screenshots: Dict[str, str] = Field(default_factory=dict)
    disclosed_date: int | None = None
    report_url: str = ""

def process_content(content, title, reported_to, reported_by, bounty, weaknesses, disclosed_date, severity_score):
    FILTER_OUT = ["Unwrap lines Copy Download"]

    content_str = ""
    screenshots = {}
    image_id = 0
    for line in content.split("\n"):
        if any(f in line for f in FILTER_OUT):
            continue

        if re.search(r"s3.*\.amazonaws\.com", line):
            name = "image_" + str(image_id)
            screenshots[name] = line
            content_str += "<" + name + ">" + "\n"
            image_id += 1
        else:
            content_str += line + "\n"

    return ReportContent(
        reported_to=reported_to,
        reported_by=reported_by,
        title=title,
        content=content_str,
        severity=severity_score,
        bounty=bounty,
        weaknesses=weaknesses,
        screenshots=screenshots,
        disclosed_date=disclosed_date
    )

async def parse_report_metadata(page) -> Tuple[str, str, str, float | None, List[str], str | None, Tuple[float, float | None]]:
    try:
        summary_sidebar = await page.query_selector(".spec-metadata-sidebar-summary-header")
        content_sidebar = await page.query_selector(".spec-metadata-sidebar-content")
        
        title_element = await page.query_selector(".report-heading__report-title div.break-word")
        title = await title_element.text_content() if title_element else ""

        # Extract reported_to
        reported_to_element = await summary_sidebar.query_selector(".spec-reported-to-meta-item .ahref")
        reported_to = await reported_to_element.text_content() if reported_to_element else "Unknown"
        
        # Extract reported_by
        reported_by_element = await summary_sidebar.query_selector(".spec-reporter .spec-reporter-link")
        reported_by = await reported_by_element.text_content() if reported_by_element else "Unknown"
            
        # Extract severity
        severity_element = await summary_sidebar.query_selector(".spec-severity-rating")
        severity = await severity_element.text_content() if severity_element else None
        
        # Extract severity score range
        severity_score_element = await summary_sidebar.query_selector(".spec-severity-score")
        severity_score_text = await severity_score_element.text_content() if severity_score_element else ""
        
        # Parse the severity score text into a tuple
        severity_score = (0.0, None)  # Default value
        if severity_score_text:
            try:
                # Remove parentheses and whitespace
                clean_score = severity_score_text.strip().strip("()").strip()
                if "~" in clean_score:
                    # It's a range like "4 ~ 6.9"
                    parts = clean_score.split("~")
                    severity_score = (float(parts[0].strip()), float(parts[1].strip()))
                else:
                    # It's a single value like "9.1"
                    severity_score = (float(clean_score), None)
            except Exception:
                severity_score = None
        
        # Extract bounty (not in the provided HTML, would need additional selector)
        bounty_element = await content_sidebar.query_selector(".spec-bounty-amount") if content_sidebar else None
        bounty_text = await bounty_element.text_content() if bounty_element else None
        bounty = float(bounty_text.replace("$", "").replace(",", "")) if bounty_text else None
        
        # Extract weaknesses properly
        weaknesses = []
        weaknesses_section = await content_sidebar.query_selector(".spec-weakness-meta-item")
        weakness_spans = await weaknesses_section.query_selector_all("span")
        for span in weakness_spans:
            weakness_text = await span.inner_text()
            if weakness_text:
                weaknesses.append(weakness_text.strip())
        
        def date_to_timestamp(date_str):
            # Handle both "5pm" and "11:00AM" formats
            try:
                # First try the standard format with minutes
                dt = datetime.strptime(date_str, "%B %d, %Y, %I:%M%p UTC")
            except ValueError:
                try:
                    # Try alternate format without minutes
                    dt = datetime.strptime(date_str, "%B %d, %Y, %I%p UTC")
                except ValueError:
                    # If both fail, log the error and return None
                    logger.error(f"Could not parse date string: {date_str}")
                    return None
            
            # Convert to Unix timestamp (seconds since epoch)
            return int(dt.timestamp())

        # Extract disclosed date
        disclosed_date_element = await content_sidebar.query_selector(".spec-disclosure-information")
        disclosed_span = await disclosed_date_element.query_selector("span")
        disclosed_date = date_to_timestamp(await disclosed_span.inner_text())
        
        return title, reported_to, reported_by, bounty, weaknesses, disclosed_date, severity_score
        
    except Exception as e:
        import sys
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = exc_tb.tb_frame.f_code.co_filename
        logger.error(f"Error in {fname} at line {exc_tb.tb_lineno}: {str(e)}")
        raise

async def parse_report_block(element, class_name):
    content = ""
    code_block = await element.query_selector(".interactive-markdown__code")
    if code_block:
        # Handle code blocks
        code_content = await element.query_selector(".interactive-markdown__code__content.interactive-markdown__code__content__wrap")
        if code_content:
            # Get spans without line numbers
            code_spans = await code_content.query_selector_all("span:not([class*='linenumber'])")
            for span in code_spans:
                span_text = await span.inner_text()
                content += span_text
            content += "\n"
        # Handle image blocks
        else:
            # Look for images recursively
            img = await element.query_selector("img")
            if img:
                src = await img.get_attribute("src")
                content += src + "\n"
    else:
        try:
            # Extract inner text for paragraphs and user content
            text = await element.inner_text()
            content += text + "\n"
        except:
            pass

    return content

async def extract_report_content(page, report_url):
    """
    Extract content from a HackerOne report page by finding the interactive-markdown element
    and its child elements.
    """                    
    content = ""
    try:
        # Wait for the interactive-markdown element to load
        await page.wait_for_selector("div[class='interactive-markdown']", timeout=REPORT_TIMEOUT)
        
        # TODO: currently we are only getting the first comment of the report and
        # ignoring followup comments
        # Get the interactive-markdown element
        markdown_element = await page.query_selector("div[class='interactive-markdown']")
        if markdown_element:
            # Get all child elements
            child_elements = await markdown_element.query_selector_all(">*")

            # Extract content based on element class
            for element in child_elements:
                class_name = await element.get_attribute("class")
                
                # Handle list elements (ul, ol)
                tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                if tag_name in ["ul", "ol"]:
                    list_items = await element.query_selector_all("li")
                    for item in list_items:
                        # Try to get class, but process item regardless
                        item_class = await item.get_attribute("class") or ""
                        block = await parse_report_block(item, item_class)                        
                        if block:
                            content += block
                else:
                    content += await parse_report_block(element, class_name)
        
        title, reported_to, reported_by, bounty, weaknesses, disclosed_date, severity_score = await parse_report_metadata(page)
        return process_content(content, title, reported_to, reported_by, bounty, weaknesses, disclosed_date, severity_score)
    
    except Exception as e:
        logger.error(f"Error extracting report content: {e}")

async def init_browser():
    # Initialize browser with custom config
    browser_config = BrowserConfig(
        headless=False,  # Set to True for headless mode
        disable_security=True,
        extra_chromium_args=[
            "--window-size=1920,1080",
        ]
    )
    browser = Browser(config=browser_config)
    # Create a new browser context with default config
    context = await browser.get_playwright_browser()
    
    # Create a single page that we'll reuse
    page = await context.new_page()
    return browser, page

async def scrape_reports(start_index=0):
    """
    Extract report URLs from HackerOne Hacktivity page
    """
    # Initialize browser with custom config
    browser_config = BrowserConfig(
        headless=False,  # Set to True for headless mode
        disable_security=True,
        extra_chromium_args=[
            "--window-size=1920,1080",
        ],
        # proxy_server="http://147.79.78.153:3128",
        _force_keep_browser_alive=True
    )
    browser = Browser(config=browser_config)
    try:
        # Create a new browser context with default config
        context = await browser.get_playwright_browser()
        
        # Create a single page that we'll reuse
        page = await context.new_page()
        
        for i in range(start_index, 400):
            target_url = REPORT_PAGE.format(index=i)
            
            # Navigate to HackerOne Hacktivity page using existing page
            logger.info(f"Navigating to {target_url}")
            
            # Set a longer timeout for navigation (30 seconds)
            await page.goto(target_url, timeout=30000, wait_until="networkidle")
            
            # Wait for content to load
            logger.info("Waiting for content to load...")
            await page.wait_for_selector("div.pb-spacing-12.md\\:pb-0", timeout=30000)
            
            # Get the page content
            content = await page.content()
            
            # Extract report URLs using regex
            logger.info("Extracting report URLs...")
            pattern = r'href="/reports/(\d+)"'
            matches = re.findall(pattern, content)
            
            if not matches:
                logger.warning("No report URLs found. The page might have changed structure.")
                        
            # Print unique report URLs
            unique_ids = set(matches)
            logger.info(f"Found {len(unique_ids)} unique report URLs")
            errord_reports = []
            for report_id in unique_ids:
                try:
                    logger.info(f"Processing report {report_id}...")
                    
                    report_url = f"https://hackerone.com/reports/{report_id}"
                    report_json = f"{OUT_DIR}/{report_id}.json"
                    content = await extract_report_content(page, report_url)
                    if content:
                        content.report_url = report_url
                        logger.info("Processing success, writing to JSON:")
                        with open(report_json, "w") as f:
                            json.dump(content.model_dump(), f, indent=2)

                    # return unique_ids
                    time.sleep(max(0, random.normalvariate(2, 1.4)))
                except Exception as e:
                    logger.error(f">>>>>>>>>>> ??? >>>> Error processing report {report_url}: {e}", exc_info=True)
                    errord_reports.append(report_url)
                    continue

        # Close the page after the loop
        # await page.close()

        with open("errord_reports.txt", "w") as f:
            f.write("\n".join(errord_reports))
            
    except Exception as e:
        logger.error(f"Error extracting report URLs: {e}")
        raise
    finally:
        # Close the browser
        logger.info("Closing browser...")
        await browser.close()

        with open("last_index.txt", "w") as f:
            f.write(str(i))

async def main():
    """Main function to run the script"""
    start_index = int(open("last_index.txt", "r").read())
    await scrape_reports(start_index=start_index)

# if __name__ == "__main__":
#     asyncio.run(main())

if __name__ == "__main__":
    async def test_reports():
        browser, page = await init_browser()


        TEST_URLS = [
            # "https://hackerone.com/reports/1032610"
            # "https://hackerone.com/reports/1032610"
            # "https://hackerone.com/reports/1457471"
            "https://hackerone.com/reports/270981"
        ]


        for url in TEST_URLS:
            await page.goto(url, timeout=30000, wait_until="networkidle")

            report_content = await extract_report_content(page, url)
            from lxml import html
            from bs4 import BeautifulSoup
            import requests

            res = requests.get(url)
            soup = BeautifulSoup(await page.content(), 'html.parser')
            text = soup.get_text(strip=True)
            print(text)

            # Get the HTML content from the page
            # html_content = await page.content()

            # # Extract just the text content
            # tree = html.fromstring(html_content)
            # text_content = tree.text_content()
            # print(text_content)

            # print(report_content.content)
            # print(report_content.screenshots)

            # with open("test_report.json", "w") as f:
            #     json.dump(report_content.model_dump(), f, indent=2)
            break
        
        await browser.close()

    asyncio.run(test_reports())