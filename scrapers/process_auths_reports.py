from johnllm import LLMModel, LMP
from pydantic import BaseModel
from enum import Enum
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from random import shuffle
import time

class Detectable(BaseModel):
    idor_detectable: bool
    authnz_byppass_detectable: bool

class CategorizeReports(LMP):
    prompt = """
{{report}}

Okay here are two proposed metholodogies for finding a certain class of authN/authZ bugs: * *
Vulnerability Name: IDOR 
- checking every combination of (user_id, action, resource_id) possible. For example this could be user A editing the invite link for a chat room (via POST /room/<room_id>) created by user B. this represents the basic IDOR vulnerability class
* Detection Method: collecting (user_a, action, resource_id) pair via HTTP requests (that is, requests using user_a's authenticated session), swapping out the original user_a for user_b, a non-privledged (in this case, an user_id that should not have access to the resource_id) user and testing if the resource authorization boundary can be crossed
Vulnerability Name: AuthN/AuthZ Bypass
- given a session/no session, a user is able to access a page or functionality that they should not be able to access ie. regular user accessing the admin panel. so similar to the above, but this time, the authorization boundary being crossed is at a functional/usage level. this would include openredirect vulns where access is granted to page normally closed off to the user by using the redirect URL
* Detection Method: collecting (user_a, action) or (user_a, navigation), and swapping out the original user_a for user_b, a non-privledged user, and testing if the action/navigation authorization boundary can be crossed

Is the vulnerability in the report above detectable using the two detection methodologies proposed?
"""
    response_format = Detectable

def classify_report(llm_model: LLMModel, report) -> Detectable:
    report_str = f"Title: {report['title']}"
    report_str += f"Description: \n{report['content']}"
    
    return CategorizeReports().invoke(
        model=llm_model,
        model_name="claude3.7",
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
        with open(report_file, "r") as f:
            report = json.load(f)
            if not report:
                continue

            report["_file"] = report_file  # Store filename for later
            batch.append(report)
            
        if len(batch) >= batch_size:
            yield batch
            batch = []
            
    if batch:  # Yield any remaining reports
        yield batch

def process_reports_in_batches(batch_num=8, max_workers=8, batch_size=50, reports_dir=Path("scrapers/authnz")):
    batch_index = 0
    llm = LLMModel()

    def process_report(report, pbar):
        result = classify_report(llm, report)
        report["idor_detectable"] = result.idor_detectable
        report["authnz_byppass_detectable"] = result.authnz_byppass_detectable
        
        with open(report["_file"], "w") as f:
            print(f"Report {report['_file']} - IDOR detectable: {result.idor_detectable}, AuthNZ bypass detectable: {result.authnz_byppass_detectable}")
            # Remove temp filename before saving
            report_to_save = report.copy()
            del report_to_save["_file"]
            time.sleep(30)
            json.dump(report_to_save, f, indent=2)
        
        pbar.update(1)
        return result.idor_detectable

    print(f"Processing {batch_num * batch_size} reports in")

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
    process_reports_in_batches(reports_dir=Path("scrapers/authnz"), max_workers=1, batch_num=8, batch_size=50)
