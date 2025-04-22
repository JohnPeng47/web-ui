from johnllm import LLMModel, LMP
from pydantic import BaseModel
import json
from pathlib import Path
from typing import Optional
from tqdm import tqdm
import asyncio
from bs4 import BeautifulSoup

from .hackerone import init_browser, extract_report_content


# TODO: once labeled, run again with all examples
# to rank them in order of complexity
class Bounty(BaseModel):
    amount: Optional[int]
    
class CategorizeReports(LMP):
    prompt = """
{{report}}

Extract the amount paid out for this bounty. If no bounty, set it as null
"""
    response_format = Bounty

def classify_report(llm_model: LLMModel, report_text: str) -> Bounty:
    # Assuming CategorizeReports().invoke is async
    # Note: The prompt now just takes {{report}}, make sure CategorizeReports handles plain text
    return CategorizeReports().invoke(
        model=llm_model,
        model_name="gpt-4o-mini", # Or your preferred model
        prompt_args={
            "report": report_text
        }
    )

def get_report_files(reports_dir: Path):
    """Returns a list of report files from the directory"""
    print(list(reports_dir.glob("*.json")))
    return list(reports_dir.glob("*.json"))

async def process_report(report_file, page, llm):
    """Processes a single report file."""
    try:
        # Load the report
        with open(report_file, "r") as f:
            report = json.load(f)
            
        if not report or "report_url" not in report:
            print(f"Skipping invalid report file: {report_file.name}")
            return None

        print(f"Processing: {report.get('title', report_file.name)}")
        
        await page.goto(report["report_url"], timeout=60000, wait_until="networkidle")
        await extract_report_content(page, report["report_url"])

        soup = BeautifulSoup(await page.content(), "html.parser")
        text = soup.get_text(strip=True)

        # print(">>>>>>>>>>>>>>>>>>>>>>>>")
        # print(text)
        # print(">>>>>>>>>>>>>>>>>>>>>>>>")

        # Call LLM for classification
        result = classify_report(llm, text)
        report["bounty"] = result.amount
        if result.amount is not None:
            print(f"Bounty found: {result.amount} for {report_file.name}")
        else:
            print(f"No bounty found for {report_file.name}")

        # Save the updated report
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        return result.amount

    except Exception as e:
        print(f"Error processing {report_file.name}: {type(e).__name__} - {str(e)}")
        return None

async def process_reports(reports_dir, page, max_reports=None):
    """Process reports one at a time."""
    llm = LLMModel()  # Initialize LLM model once
    
    report_files = get_report_files(reports_dir)
    if max_reports:
        report_files = report_files[:max_reports]
        
    print(f"Processing {len(report_files)} reports")
    
    results = []
    with tqdm(total=len(report_files), desc="Processing Reports") as pbar:
        for report_file in report_files:
            try:
                result = await process_report(report_file, page, llm)
                results.append(result)
                pbar.update(1)
            except Exception as e:
                print(f"Error during processing: {type(e).__name__} - {str(e)}")

    print(f"\nFinished processing. Total reports processed: {len(report_files)}")
    return results

async def main():
    browser = None  # Initialize browser variable
    try:
        browser, page = await init_browser()
        reports_path = Path("scrapers/high_reports")  # Define path
        # Ensure the directory exists
        if not reports_path.is_dir():
            print(f"Error: Reports directory not found at {reports_path}")
            return

        # Process just one report for testing
        await process_reports(reports_path, page)
        # For processing more reports:
        # await process_reports(reports_path, page, max_reports=10)

    except Exception as e:
        print(f"An error occurred in main: {e}")
    finally:
        if browser:
            print("Closing browser...")
            await browser.close()
            print("Browser closed.")

if __name__ == "__main__":
    import logging
    
    # Configure logging to debug level
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    logger.debug("Debug logging enabled")

    # Handle potential asyncio errors on Windows during shutdown
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Process interrupted by user.")
    finally:
        # This is a common pattern to help mitigate asyncio cleanup issues on Windows
        # See: https://github.com/aio-libs/aiohttp/issues/4324
        # And: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.ProactorEventLoop
        if asyncio.get_event_loop().is_running():
             asyncio.get_event_loop().stop()
        if not asyncio.get_event_loop().is_closed():
             # Give tasks a moment to clean up before force closing loop
             # asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1)) # Optional delay
             asyncio.get_event_loop().close()

