from pathlib import Path
import json
from collections import Counter
from enum import Enum
from typing import List, Union

import time
import sys
from pydantic import BaseModel
from johnllm import LLMModel, LMP
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from random import shuffle
from pydantic import BaseModel


AUTHORIZATION = [
    "Improper Access Control - Generic",
    "Insecure Direct Object Reference (IDOR)",
    "Improper Authentication - Generic", 
    "Authentication Bypass Using an Alternate Path or Channel",
    "Improper Authorization",
    "Authentication Bypass",
    "Missing Critical Step in Authentication",
    "Incorrect Authorization",
    "Improper Privilege Management",
    "Incorrect Privilege Assignment",
    "Privilege Escalation",
]

class VulnCategory(str, Enum):
    WEB_APP = "WEB_APP"
    API = "API"

class SeverityLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Weaknesses(str, Enum):
    XSS = "XSS"
    AUTHZ_AUTN = "AUTHZ/AUTN"
    OTHER_INJECTION = "OTHER_INJECTION"
    SSRF = "SSRF"
    OTHER = "OTHER"
    CODE_VULNS_IGNORE = "CODE_VULNS_IGNORE"
    IDK = "IDK"

def convert_weakness(weakness):
    ISSUES_MAPPING = {
        Weaknesses.XSS: [
            "Cross-site Scripting (XSS) - Stored",
            "Cross-site Scripting (XSS) - DOM", 
            "Cross-site Scripting (XSS) - Reflected",
            "Cross-site Scripting (XSS) - Generic",
            "Reflected XSS"
        ],
        Weaknesses.AUTHZ_AUTN: [
            "Improper Access Control - Generic",
            "Insecure Direct Object Reference (IDOR)",
            "Improper Authentication - Generic", 
            "Authentication Bypass Using an Alternate Path or Channel",
            "Improper Authorization",
            "Authentication Bypass",
            "Missing Critical Step in Authentication",
            "Incorrect Authorization",
            "Improper Privilege Management",
            "Incorrect Privilege Assignment",
            "Privilege Escalation",
        ],
        Weaknesses.OTHER_INJECTION : [
            "SQL Injection",
            "Blind SQL Injection",
            "Command Injection - Generic",
            "OS Command Injection",
            "Code Injection",
            "XML External Entities (XXE)",
            "Resource Injection",
            "XML Injection",
            "LDAP Injection",
            "Use of Externally-Controlled Format String",
            "Remote File Inclusion",
            "PHP Local File Inclusion"
        ],
        Weaknesses.SSRF: [
            "Server-Side Request Forgery (SSRF)"
        ],
        Weaknesses.OTHER : [
            "Information Disclosure",
            "Path Traversal",
            "Business Logic Errors",
            "Cross-Site Request Forgery (CSRF)",
            "Violation of Secure Design Principles",
            "HTTP Request Smuggling",
            "Insecure Storage of Sensitive Information",
            "Cryptographic Issues - Generic",
            "Improper Restriction of Authentication Attempts",
            "Improper Input Validation",
            "Cleartext Storage of Sensitive Information",
            "Information Exposure Through Directory Listing",
            "Misconfiguration",
            "Privacy Violation",
            "Insufficiently Protected Credentials",
            "Open Redirect",
            "UI Redressing (Clickjacking)",
            "Improper Certificate Validation",
            "Phishing",
            "Path Traversal: '.../.../'",
            "Man-in-the-Middle",
            "Weak Password Recovery Mechanism for Forgotten Password",
            "Use of Hard-coded Credentials",
            "Missing Encryption of Sensitive Data",
            "Information Exposure Through Debug Information",
            "Unverified Password Change",
            "Session Fixation",
            "CRLF Injection",
            "HTTP Response Splitting",
            "Security Through Obscurity",
            "Reliance on Cookies without Validation and Integrity Checking in a Security Decision",
            "Unrestricted Upload of File with Dangerous Type",
            "Insufficient Session Expiration",
            "File and Directory Information Exposure",
            "Information Exposure Through an Error Message",
            "User Interface (UI) Misrepresentation of Critical Information",
            "Malware",
            "Password in Configuration File",
            "Storing Passwords in a Recoverable Format",
            "Leftover Debug Code (Backdoor)",
            "Use of a Broken or Risky Cryptographic Algorithm",
            "Externally Controlled Reference to a Resource in Another Sphere",
            "Weak Cryptography for Passwords",
            "Reusing a Nonce, Key Pair in Encryption",
            "Information Exposure Through Sent Data",
            "Improper Check or Handling of Exceptional Conditions",
            "Untrusted Search Path",
            "Use of Cryptographically Weak Pseudo-Random Number Generator (PRNG)",
            "Use of Cache Containing Sensitive Information",
            "Use of Default Credentials",
            "Cleartext Transmission of Sensitive Information",
            "Use of a Key Past its Expiration Date",
            "Plaintext Storage of a Password",
            "Forced Browsing",
            "Encoding Error",
            "Inclusion of Functionality from Untrusted Control Sphere",
            "File Manipulation",
            "Using Components with Known Vulnerabilities",
            "Key Exchange without Entity Authentication",
            "Missing Required Cryptographic Step",
            "Embedded Malicious Code",
            "XML Entity Expansion",
            "Use of Hard-coded Cryptographic Key",
            "Reliance on Untrusted Inputs in a Security Decision",
            "Exposed Dangerous Method or Function",
            "Improper Handling of URL Encoding (Hex Encoding)",
            "Download of Code Without Integrity Check",
            "Use of Hard-coded Password"
        ],
        Weaknesses.CODE_VULNS_IGNORE : [
            "Memory Corruption - Generic",
            "Buffer Over-read",
            "Classic Buffer Overflow",
            "Heap Overflow",
            "Use After Free",
            "Out-of-bounds Read",
            "Stack Overflow",
            "NULL Pointer Dereference",
            "Buffer Underflow",
            "Integer Overflow",
            "Improper Null Termination",
            "Double Free",
            "Array Index Underflow",
            "Use of Inherently Dangerous Function",
            "Type Confusion",
            "Write-what-where Condition",
            "Incorrect Calculation of Buffer Size",
            "Off-by-one Error",
            "Uncontrolled Resource Consumption",
            "Deserialization of Untrusted Data",
            "Allocation of Resources Without Limits or Throttling",
            "Time-of-check Time-of-use (TOCTOU) Race Condition",
            "Modification of Assumed-Immutable Data (MAID)",
            "External Control of Critical State Data"
        ],
        Weaknesses.IDK : [
            "None",
            "Other"
        ]

    }
    # Check if weakness matches any values in the mapping
    for key, values in ISSUES_MAPPING.items():
        if weakness in values:
            return key
            
    # Return original weakness if no match found
    return weakness

def map_severity_to_level(severity: Union[List[float], None]) -> str:
    """Map severity scores to standardized levels
    
    Args:
        severity: List of severity scores or None
    Returns:
        Severity level string
    """
    if not severity:  # Handle None or empty list
        return SeverityLevel.LOW.value
        
    # Filter out None values and convert to float
    valid_scores = [float(score) for score in severity if score is not None]
    
    if not valid_scores:  # If no valid scores after filtering
        return SeverityLevel.LOW.value
    
    # Use the highest severity score
    max_severity = max(valid_scores)
    
    if max_severity >= 7.0:
        return SeverityLevel.HIGH.value
    elif max_severity >= 4.0:
        return SeverityLevel.MEDIUM.value
    else:
        return SeverityLevel.LOW.value
    
def classify_report(llm_model: LLMModel, lmp: LMP, report, model_name):
    report_str = f"Title: {report['title']}"
    report_str += f"Description: \n{report['content']}"
    
    return lmp().invoke(
        model=llm_model,
        model_name=model_name,
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

def process_reports_in_batches(reports_dir, 
                               lmp: LMP, 
                               batch_size=50, 
                               max_workers=4, 
                               model_name="deepseek-reasoner",
                               total_reports=None):   
    batch_index = 0
    llm = LLMModel()
    # Calculate the number of batches based on the number of reports
    all_reports = len(list(reports_dir.glob("*.json")))
    
    # If total_reports is specified, use the smaller of total_reports or all_reports
    if total_reports is not None:
        all_reports = min(all_reports, total_reports)
        
    batch_num = (all_reports + batch_size - 1) // batch_size
    print(f"Using calculated batch_num: {batch_num}")

    def process_report(report, pbar):
        try:
            # if report.get("new_complexity", None):
            #     print("Skipping report: ", report["_file"])
            #     pbar.update(1)
            #     return
            
            result = classify_report(llm, lmp, report, model_name)
            
            # Check if result is a pydantic model
            if not isinstance(result, BaseModel):
                raise TypeError(f"Expected Pydantic BaseModel, got {type(result).__name__}")
            
            print(f"Report {report['_file']}")
            # Iterate through all fields in the result model and add to report
            for field_name in result.__fields__:
                # TODO: turn this on later
                # Check if field already exists in report
                # if field_name in report:
                #     print(f"Error: Field '{field_name}' already exists in report {report['_file']}")
                #     sys.exit(1)

                report[field_name] = getattr(result, field_name)
                print(getattr(result, field_name))
            with open(report["_file"], "w") as f:
                # Remove temp filename before saving
                report_to_save = report.copy()
                del report_to_save["_file"]
                json.dump(report_to_save, f, indent=2)
            
            pbar.update(1)
            return result

        except Exception as e:
            print(f"Error processing {report['_file'].name}: {str(e)}")
            pbar.update(1)

    # Calculate total reports to process
    reports_to_process = batch_num * batch_size
    if total_reports is not None:
        reports_to_process = min(reports_to_process, total_reports)
    
    print(f"Processing {reports_to_process} reports")
    print("total_reports", total_reports)
    print("batch_num", batch_num)

    # Create the generator once outside the loop
    batch_generator = read_reports_in_batches(reports_dir, batch_size=batch_size)
    processed_reports = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while batch_index < batch_num:
            try:
                # Get next batch
                batch = next(batch_generator)
                
                # If total_reports is specified, limit the batch size
                # if total_reports is not None:
                #     remaining = total_reports - processed_reports
                #     if remaining <= 0:
                #         break
                #     if len(batch) > remaining:
                #         batch = batch[:remaining]
                
                with tqdm(total=len(batch), desc=f"Processing batch {batch_index + 1}/{batch_num}") as pbar:
                    results = list(executor.map(lambda x: process_report(x, pbar), batch))
                
                processed_reports += len(batch)
                batch_index += 1
                print(f"Processed {batch_index} batches")
                
                # Check if we've reached the total_reports limit
                # if total_reports is not None and processed_reports >= total_reports:
                #     break
                    
            except StopIteration:
                print("No more batches to process")
                break
