from pathlib import Path
import json
from enum import Enum
import random

class VulnCategory(str, Enum):
    WEB_APP = "WEB_APP"
    API = "API"

class SeverityLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


def map_severity_to_level(severity) -> str:
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

def collect_high_webapp_reports(reports_dir: Path, output_file: Path):
    """Collect vulnerability reports grouped by complexity/novelty and multi-component status
    
    Args:
        reports_dir: Directory containing report JSON files
        output_file: Path to write output report to
    """
    # Initialize groups
    high_multi = []
    high_single = []
    low_multi = []
    low_single = []
    
    # Process all JSON files and collect reports
    for report_file in reports_dir.glob("*.json"):
        with open(report_file, "r", encoding="utf-8") as f:
            try:
                report = json.load(f)
                category = report.get("vuln_category")
                
                # Skip if not WEB_APP
                if category != VulnCategory.WEB_APP:
                    continue
                
                # Skip if not HIGH severity
                # severity = map_severity_to_level(report.get("severity"))
                # if severity != SeverityLevel.HIGH.value:
                #     continue
                    
                # if report.get("is_ctf", False):
                #     continue
                
                # Determine if high complexity/novelty
                is_high = (report.get("complexity") == "HIGH" or report.get("novelty") == "HIGH")
                is_multi = report.get("is_multi_component", False)
                
                # Add to appropriate group with the full report and filename
                if is_high and is_multi:
                    print(f"Adding high complexity multi-component report: {report_file}")
                    high_multi.append((report_file, report))
                elif is_high and not is_multi:
                    print(f"Adding high complexity single-component report: {report_file}")
                    high_single.append((report_file, report))
                elif not is_high and is_multi:
                    print(f"Adding low/medium complexity multi-component report: {report_file}")
                    low_multi.append((report_file, report))
                else:
                    print(f"Adding low/medium complexity single-component report: {report_file}")
                    low_single.append((report_file, report))
                    
            except json.JSONDecodeError:
                print(f"Error reading {report_file}")
                continue

    # Create output directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write reports to file
    with open(output_file, "w", encoding="utf-8") as outf:
        groups = [
            ("HIGH COMPLEXITY/NOVELTY MULTI-COMPONENT REPORTS", high_multi),
            ("HIGH COMPLEXITY/NOVELTY SINGLE-COMPONENT REPORTS", high_single),
            ("LOW/MEDIUM COMPLEXITY/NOVELTY MULTI-COMPONENT REPORTS", low_multi),
            ("LOW/MEDIUM COMPLEXITY/NOVELTY SINGLE-COMPONENT REPORTS", low_single)
        ]
        
        for title, group in groups:
            outf.write(f"\n{title}\n")
            outf.write("=" * 50 + "\n\n")
            
            # Randomly select up to 15 reports
            selected = random.sample(group, min(15, len(group)))
            outf.write(f"Total reports in group: {len(group)}\n")
            outf.write(f"Selected reports: {len(selected)}\n\n")
            
            for report_file, report in selected:
                weaknesses = report.get("weaknesses", [])
                if isinstance(weaknesses, str):
                    weaknesses = [weaknesses]
                
                outf.write(f"Report File: {report_file.name}\n")
                outf.write("-" * 30 + "\n")
                outf.write(f"Report To: {report.get('reported_to', 'Not specified')}\n")
                outf.write(f"Severity: {map_severity_to_level(report.get('severity'))}\n")
                outf.write(f"Complexity: {report.get('complexity', 'Not specified')}\n")
                outf.write(f"Novelty: {report.get('novelty', 'Not specified')}\n")
                outf.write(f"Multi-component: {report.get('is_multi_component', False)}\n")
                outf.write("Weaknesses:\n")
                for weakness in weaknesses:
                    outf.write(f"- {weakness}\n")
                outf.write("\nContents:\n")
                outf.write(f"{report.get('content', 'No contents available')}\n")
                outf.write("\n" + "=" * 50 + "\n\n")

    print(f"Reports have been written to {output_file}")

if __name__ == "__main__":
    reports_dir = Path("scrapers/high_reports")
    output_file = Path("analysis/multi_analysis/WEBAPP_ANALYSIS.txt")
    collect_high_webapp_reports(reports_dir, output_file)