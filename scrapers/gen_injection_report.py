import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any


def analyze_injection_reports(input_dir: str, output_file: str, title: str = "Injection Vulnerabilities Analysis"):
    """
    Analyzes all reports in the specified directory
    and writes their vulnerability descriptions and steps to a file.
    """
    reports_count = 0
    reports_dir = Path(input_dir)
    output_path = Path(output_file)
    
    # Store reports by category
    categorized_reports: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    # Process all report files
    for report_file in reports_dir.glob("*.json"):
        try:
            with open(report_file, "r") as f:
                report = json.load(f)
                
                # Check if report has weaknesses
                if not report.get("weaknesses"):
                    continue
                
                reports_count += 1
                
                # Categorize by weakness type
                for weakness in report.get("weaknesses", []):
                    category = weakness  # Use the weakness directly as category
                    categorized_reports[category].append(report)
                    break  # Only add the report once

        except Exception as e:
            print(f"Error processing {report_file}: {e}")
    
    print("Total reports analyzed:", reports_count)
    
    # Write results to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"{title}\n")
        f.write("==================================================\n\n")
        
        total_reports = sum(len(reports) for reports in categorized_reports.values())
        f.write(f"Total reports analyzed: {total_reports}\n\n")
        
        for category, reports in categorized_reports.items():
            f.write(f"{category} Vulnerabilities ({len(reports)} reports)\n")
            f.write("-" * 50 + "\n\n")
            
            for i, report in enumerate(reports, 1):
                f.write(f"Report {report.get('report_url')}: {report.get('title', 'No Title')}\n")
                f.write("=" * 80 + "\n")
                
                f.write("RAW DESCRIPTION:\n")
                f.write(f"{report.get('content', 'No description available')}\n\n")

                f.write("=" * 80 + "\n")

                # Write vulnerability description
                f.write("Vulnerability Description:\n")
                f.write(f"{report.get('vuln_description', 'No description available')}\n\n")
                
                # Write steps to reproduce
                f.write("Steps to Reproduce:\n")
                if report.get("steps"):
                    for step_num, step_desc in report.get("steps", []):
                        f.write(f"{step_num}. {step_desc}\n")
                else:
                    f.write("No steps available\n")
                
                f.write("Exploitation Difficulty:\n")
                f.write(report.get("reason", "None") + "\n")

                f.write("\n" + "-" * 80 + "\n\n")
            
            f.write("\n\n")
    
    print(f"Analysis complete. Results written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate injection vulnerability report from JSON files")
    parser.add_argument("input_dir", help="Directory containing JSON report files")
    parser.add_argument("output_file", help="Output file path for the analysis report")
    parser.add_argument("--title", default="Injection Vulnerabilities Analysis", 
                        help="Title for the analysis report")
    
    args = parser.parse_args()
    
    analyze_injection_reports(args.input_dir, args.output_file, args.title)


if __name__ == "__main__":
    main()
