from pathlib import Path
import json
import os

from .utils import convert_weakness, Weaknesses


def clean_authnz_metadata():
    """
    Iterates through all JSON files in scrapers/high_reports directory
    and removes the 'authnz_metadata' field from each file.
    """
    reports_dir = Path("scrapers/high_reports")
    processed_count = 0
    
    # Process all report files
    for report_file in reports_dir.glob("*.json"):
        try:
            with open(report_file, "r") as f:
                report = json.load(f)
                if not report:
                    continue
                        

            # Check if the report has the authnz_metadata field
            if "authnz_metadata" in report:
                # Remove the field
                del report["authnz_metadata"]
                processed_count += 1
                
                # Write the updated report back to the file
                with open(report_file, "w") as f:
                    json.dump(report, f, indent=2)
        
        except Exception as e:
            print(f"Error processing {report_file}: {e}")
    
    print(f"Processed {processed_count} reports, removed 'authnz_metadata' field")

if __name__ == "__main__":
    clean_authnz_metadata()
