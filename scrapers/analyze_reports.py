from pathlib import Path
import json
from enum import Enum

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
    """Collect all HIGH severity WEB_APP vulnerability reports and write to file
    
    Args:
        reports_dir: Directory containing report JSON files
        output_file: Path to write output report to
    """
    # Track weakness counts and total reports
    weakness_counts = {}
    high_severity_count = 0
    
    # Process all JSON files and collect HIGH severity WEB_APP reports
    with open(output_file, "w", encoding="utf-8") as outf:
        outf.write("HIGH SEVERITY WEB APPLICATION VULNERABILITY REPORTS\n")
        outf.write("=" * 50 + "\n\n")
        
        for report_file in reports_dir.glob("*.json"):
            with open(report_file, "r", encoding="utf-8") as f:
                try:
                    report = json.load(f)
                    category = report.get("target_category")
                    
                    # Skip if not WEB_APP
                    if category != VulnCategory.WEB_APP.value:
                        continue
                    
                    # Skip if not HIGH severity
                    severity = map_severity_to_level(report.get("severity"))
                    if severity != SeverityLevel.HIGH.value:
                        continue
                        
                    if report.get("is_ctf", True):
                        continue
                    
                    # Increment high severity count
                    high_severity_count += 1
                    
                    # Update weakness counts
                    weaknesses = report.get("weaknesses", [])
                    if isinstance(weaknesses, str):  # Handle case where it might be a string
                        weaknesses = [weaknesses]
                    for weakness in weaknesses:
                        weakness_counts[weakness] = weakness_counts.get(weakness, 0) + 1
                    
                    # Write report with separator
                    outf.write(f"Report File: {report_file.name}\n")
                    outf.write("-" * 30 + "\n")
                    outf.write(f"Report To: {report.get('reported_to', 'Not specified')}\n")
                    outf.write(f"Severity: {severity}\n")
                    outf.write("Weaknesses:\n")
                    for weakness in weaknesses:
                        outf.write(f"- {weakness}\n")
                    outf.write("\nContents:\n")
                    outf.write(f"{report.get('content', 'No contents available')}\n")
                    outf.write("\n" + "=" * 50 + "\n\n")
                    
                except json.JSONDecodeError:
                    print(f"Error reading {report_file}")
                    continue

        # Add weakness statistics section at the end
        outf.write("\nWEAKNESS STATISTICS FOR HIGH SEVERITY WEB APP REPORTS\n")
        outf.write("=" * 50 + "\n\n")
        outf.write(f"Total HIGH severity reports found: {high_severity_count}\n\n")
        if weakness_counts:
            for weakness, count in sorted(weakness_counts.items(), key=lambda x: x[1], reverse=True):
                outf.write(f"{weakness}: {count} occurrence(s)\n")
        else:
            outf.write("No weaknesses found in HIGH severity WEB_APP reports\n")

    print(f"HIGH severity WEB_APP reports have been written to {output_file}")

if __name__ == "__main__":
    reports_dir = Path("scrapers/authnz")
    output_file = Path("analysis/HIGH_WEBAPP_AUTHNZ_REPORTS.txt")
    collect_high_webapp_reports(reports_dir, output_file)
