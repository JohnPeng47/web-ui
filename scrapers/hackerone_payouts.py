import json
from pathlib import Path

def extract_companies():
    """
    Extracts unique companies from the 'reported_to' field in all reports
    and writes them to companies.txt
    """
    # Path to high reports directory
    reports_dir = Path("scrapers/high_reports")
    
    # Set to store unique companies
    companies = set()
    
    # Iterate through all JSON files in the directory
    for report_file in reports_dir.glob("*.json"):
        try:
            with open(report_file, "r") as f:
                report = json.load(f)
                
                # Extract reported_to field if it exists
                if report and "reported_to" in report and report["reported_to"]:
                    companies.add(report["reported_to"])
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error reading {report_file}: {e}")
    
    # Write unique companies to companies.txt
    with open("companies.txt", "w") as f:
        for company in sorted(companies):
            f.write(f"{company}\n")
    
    print(f"Extracted {len(companies)} unique companies to companies.txt")

if __name__ == "__main__":
    extract_companies()
