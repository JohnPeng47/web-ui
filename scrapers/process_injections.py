from johnllm import LLMModel, LMP
from enum import Enum
from pathlib import Path

from .utils import process_reports_in_batches, InjectionStruct

class Level(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"

class CategorizeReports(LMP):
    prompt = """
{{report}}

Okay here is a proposed methodology for finding a class of bugs. 
# Simple Payloads
1. Find every injectable parameter on a webpage.
2. Then using a *simple* payload list that contains common permutations of payloads such as b64 encoding, context positioning for XSS, etc.,
inject the payload into the parameter and send the request
-> *simple* means a generic payload that does not include any kind of custom filter bypass
3. Payload execution can be determined within the same channel ie. for blind SQLi payloads, there is usually some way
to detect the response

Return your answer as a boolean called is_simple_payload
"""
    response_format = InjectionStruct

if __name__ == "__main__":
    process_reports_in_batches(
        Path("scrapers/high_reports"), 
        CategorizeReports, 
        model_name="deepseek-chat",
        batch_size=50, 
        max_workers=20
    )
