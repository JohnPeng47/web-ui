from johnllm import LLMModel, LMP
from pydantic import BaseModel
from enum import Enum
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from random import shuffle
import time

class Level(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

# TODO: once labeled, run again with all examples
# to rank them in order of complexity
class ClassifyMultiComponent(BaseModel):
    is_multi: bool
    complexity: Level
    novelty: Level
    
class CategorizeReports(LMP):
    prompt = """
REPORT:
{{report}}

Most vulns found in a web application pentest trigger within and affect a single component. These are usually easy to diagnose
Other vulns require multiple components to be involved in the attack. These are usually harder to detect.

Below is an example of a multi stage vuln:

Hey team,
I have discovered a way for any logged in user (attacker) to escalate his privileges to gitlab administrator if the real gitlab administrator impersonates attacker's account.
Description:
When the gitlab admin impersonates some user, he gets new _gitlab_session cookie and then clicking at Stop impersonating he gets his own admin's cookie back. The vulnerability is that the impersonated user (attacker in our case) can see impersonated session at the Active sessions so he can switch to it (manually setting it in cookie) and click Stop impersonating by himself. This is a way how he can become gitlab administrator.
Steps To Reproduce:
Sign into gitlab app as some user (attacker)
Go to the active sessions settings tab and revoke all the sessions besides the current active one
Sign into gitlab app in other browser as administrator (admin)
Go to users admin section and impersonate attacker user
<image_0>
Inspect the Revoke button and make sure you see the session ID there. Copy it. ████
Go to index page of gitlab as attacker (http://gitlab.bb/ in my case), I do not know why, but it is important step
Clear attacker browser's cookie
Open the developer console as attacker and manually set _gitlab_session to the copied one with:
Code 42 Bytes
1document.cookie = "_gitlab_session=█████";
<image_1>
Click Stop impersonating at the top-right corner as attacker and make sure you are now logged in as gitlab admin. ███
Impact
Every gitlab authenticated user can escalate his privileges to admin ones and give complete access to all gitlab services, projects and abilities. Only he needs to do is ask admin to impersonate his account because of something works bad there.

Now, given the REPORT mentioned above, classify it as:
- a multi-component vulnerability or not
- the complexity of the vulnerability (LOW, MEDIUM, HIGH)
- the novelty of the vulnerability (LOW, MEDIUM, HIGH)
"""
    response_format = ClassifyMultiComponent

def classify_report(llm_model: LLMModel, report) -> ClassifyMultiComponent:
    report_str = f"Title: {report['title']}"
    report_str += f"Description: \n{report['content']}"
    
    return CategorizeReports().invoke(
        model=llm_model,
        model_name="gpt-4o",
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

def process_reports_in_batches(reports_dir, batch_num=8, max_workers=8, batch_size=50):
    batch_index = 0
    llm = LLMModel()

    def process_report(report, pbar):
        try:
            # Skip if report already has these fields
            if all(field in report for field in ["is_multi_component", "complexity", "novelty"]):
                print(f"Skipping {report['_file'].name} - already processed")
                pbar.update(1)
                return None

            result = classify_report(llm, report)
            report["is_multi_component"] = result.is_multi
            report["complexity"] = result.complexity
            report["novelty"] = result.novelty
            
            with open(report["_file"], "w") as f:
                # Remove temp filename before saving
                report_to_save = report.copy()
                del report_to_save["_file"]
                time.sleep(30)
                json.dump(report_to_save, f, indent=2)
            
            pbar.update(1)
            return result.is_multi

        except Exception as e:
            print(f"Error processing {report['_file'].name}: {str(e)}")
            pbar.update(1)
            return None

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
    process_reports_in_batches(Path("scrapers/high_reports"), max_workers=8, batch_num=39, batch_size=50)
