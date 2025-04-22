from johnllm import LLMModel, LMP
from typing import Optional
from pydantic import BaseModel
from enum import Enum
from pathlib import Path


from .utils import process_reports_in_batches

class Level(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"

# TODO: once labeled, run again with all examples
# to rank them in order of complexity
class isCode(BaseModel):
    requires_code: bool
    requires_CVE: bool
    is_ctf: bool
    other_report: Optional[str]

class CategorizeReports(LMP):
    prompt = """
{{report}}

Given the report above, extract the following information:

requires_code: does part of the vulnerability discovery involve looking at the source code of the *backend application*?
If so, return True. Note that client-side JS code/scripts (unless its something like node) is not considered backend code
requires_CVE: does the vulnerability require a CVE to be exploited
is_ctf: is this a ctf challenge
other_report: does the writeup explicitly mention another Hackerone report? If so, put the report ID in; otherwise null
"""
    response_format = isCode

if __name__ == "__main__":
    process_reports_in_batches(Path("scrapers/high_reports"), CategorizeReports, batch_size=50, max_workers=20)
