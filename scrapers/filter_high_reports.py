from .utils import convert_weakness, Weaknesses

import json
import shutil
from pathlib import Path

def filter_medium_complex_injections():
    """
    Filters all XSS and OTHER_INJECTION reports and moves them to different directories:
    - Reports passing check (no code required) to scrapers/new_high_reports_no_code
    - Reports failing check (code required) to scrapers/new_high_code
    """
    reports_count = 0
    no_code_count = 0
    code_count = 0
    reports_dir = Path("scrapers/high_reports")
    no_code_dir = Path("scrapers/new_high_reports_no_code")
    code_dir = Path("scrapers/new_high_code")
    
    # Create target directories if they don't exist
    no_code_dir.mkdir(exist_ok=True)
    code_dir.mkdir(exist_ok=True)
    
    # Categories we're interested in
    target_categories = ["XSS", "OTHER_INJECTION"]
    
    # Process all report files
    for report_file in reports_dir.glob("*.json"):
        try:
            with open(report_file, "r") as f:
                report = json.load(f)
                
                # Check if report has weaknesses
                if not report.get("weaknesses"):
                    continue
                
                reports_count += 1
                
                # Check if report matches target categories
                for weakness in report.get("weaknesses", []):
                    category = convert_weakness(weakness)
                    if category in target_categories:
                        # Determine destination based on requirements
                        if report.get("requires_code") or report.get("requires_CVE") or report.get("is_ctf"):
                            dest_dir = code_dir
                            code_count += 1
                            print(f"Moved {report_file.name} to {code_dir}")
                        else:
                            dest_dir = no_code_dir
                            no_code_count += 1
                            print(f"Moved {report_file.name} to {no_code_dir}")
                        
                        # Copy the file to the appropriate directory
                        dest_file = dest_dir / report_file.name
                        shutil.copy2(report_file, dest_file)
                        break  # Only move the report once

        except Exception as e:
            print(f"Error processing {report_file}: {e}")
    
    print(f"Processed {reports_count} reports:")
    print(f"- {no_code_count} reports moved to {no_code_dir}")
    print(f"- {code_count} reports moved to {code_dir}")


if __name__ == "__main__":
    filter_medium_complex_injections()
