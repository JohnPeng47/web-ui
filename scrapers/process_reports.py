from johnllm import LLMModel, LMP
from pydantic import BaseModel
from enum import Enum
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from random import shuffle

class VulnCategory(str, Enum):
    WEB_APP = "WEB_APP"
    API = "API" 
    MOBILE = "MOBILE"
    IOT = "IOT"
    CODE = "CODE"

class Report(BaseModel):
    category: VulnCategory

class CategorizeReports(LMP):
    prompt = """
{{report}}

The above is a report for a vulnerability. Please categorize it into one of the following categories:

WEB_APP:  a vuln in *deployed* software. a network vulnerability that requires some interaction with a user interface (that is, this is not *strictly* required since the interface action may be triggered by an API call but the in the report the finding originates from the interface)
API: a vuln in *deployed* software. a network vulnerability that does not require some interaction with a user interface
MOBILE: all mobile originating vulnerabilities
IOT: all IOT vulns should be here, including random hardware things
CODE: the vulnerability exists *intrinsically* in some software package, rather than a deployed application. all new vulnerabilities should be categorized here. the exploitation of existing vulns in * deployed* software should either go under API or WEB_APP
"""
    response_format = Report

def classify_report(llm_model: LLMModel, report) -> Report:
    report_str = f"Title: {report['title']}"
    report_str += f"Description: \n{report['content']}"
    
    return CategorizeReports().invoke(
        model=llm_model,
        model_name="deepseek/deepseek-chat",
        prompt_args={
            "report": report_str
        }
    )

def read_reports_in_batches(reports_dir: Path, batch_size: int = 50):
    """Generator that yields batches of reports from JSON files"""
    # Shuffle order so we dont get reports all in the same date range
    report_files = list(reports_dir.glob("*.json"))
    shuffle(report_files)
    batch = []
    for report_file in report_files:
        try:
            with open(report_file, "r") as f:
                report = json.load(f)
                if not report:
                    continue
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error reading {report_file}: {e}")
            continue

        report["_file"] = report_file  # Store filename for later
        batch.append(report)
        if len(batch) >= batch_size:
            yield batch
            batch = []
            
    if batch:  # Yield any remaining reports
        yield batch

def process_reports_in_batches(reports_dir, max_workers=8, batch_size=50, batch_num=None):
    batch_index = 0
    llm = LLMModel()

    if batch_num is None:
        # Calculate the number of batches based on the number of reports
        total_reports = len(list(reports_dir.glob("*.json")))
        batch_num = (total_reports + batch_size - 1) // batch_size
        print("Using calculated batch_num:", batch_num)

    def process_report(report, pbar):
        try:
            result = classify_report(llm, report)
            report["vuln_category"] = result.category
            
            with open(report["_file"], "w") as f:
                print(f"Report {report['_file']} categorized as {result.category}")
                # Remove temp filename before saving
                report_to_save = report.copy()
                del report_to_save["_file"]
                json.dump(report_to_save, f, indent=2)
            
            pbar.update(1)
            return result.category

        except Exception as e:
            print(f"Error processing {report['_file'].name}: {str(e)}")
            pbar.update(1)
            raise e
            return None

    print(f"Processing {batch_num * batch_size} reports")

    # Create the generator once outside the loop
    batch_generator = read_reports_in_batches(reports_dir, batch_size=batch_size)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while batch_index < batch_num:
            try:
                # Get next batch
                batch = next(batch_generator)
                
                with tqdm(total=len(batch), desc=f"Processing batch {batch_index + 1}/{batch_num}") as pbar:
                    results = list(executor.map(lambda x: process_report(x, pbar), batch))
                
                batch_index += 1
                print(f"Processed {batch_index} batches")
            except StopIteration:
                print("No more batches to process")
                break

if __name__ == "__main__":
    reports_dir = Path("scrapers/high_reports")
    process_reports_in_batches(reports_dir, max_workers=10, batch_size=50)
