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

I want you to help me classify some vulnerability reports based on their difficulty to detect for a web-browsing LLM agent who behaves
in the following way:

On every step, he will execute some ACTIONS and observe the change to his ENVIRONMENT
His ACTIONS include:
- interactions with the browser (clicking, typing, etc)
- execution of scripts and other hacking tools

His ENVIRONMENT include:
- the HTML of the current webpage
- the HTTP requests/responses triggered by his interactions with the browser
- the result from script/tool execution


1. state_complexity: (LOW, MEDIUM, HIGH)
This measures the complexity of the vulnerability as the result of the different components involved in the attack, and the interactions
between them. 
This actually measures two properties, that are not nessescarily exclusive:
a) the more components involved, the more complex
b) the more subtle/non-obvious the interactions between components, the more complex it is

Here are a couple of examples:
Example 1:
state_complexity: LOW
Vulnerability: A stored XSS component 



A privilege escalation vulnerability exists in GitLab's user impersonation feature. Any authenticated user can gain administrator privileges when an admin impersonates their account.

Description:
When an admin impersonates a user, they receive a new _gitlab_session cookie. The impersonated user can view this session in their Active Sessions tab, copy the session ID, and use it to gain admin access by clicking "Stop impersonating".

Steps to Reproduce:
1. Login as the attacker user
2. In Active Sessions settings, revoke all sessions except the current one
3. In another browser, login as admin and impersonate the attacker
4. <image_0>
5. Copy the session ID from the Revoke button ████
6. As attacker, navigate to GitLab index page (http://gitlab.bb/)
7. Clear browser cookies
8. Set the copied session via console:
   document.cookie = "_gitlab_session=█████";
9. <image_1>
10. Click "Stop impersonating" - you now have admin access ███

Impact:
Any authenticated user can gain full administrator access to GitLab by having an admin impersonate their account. This grants complete access to all GitLab services, projects and capabilities.

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
