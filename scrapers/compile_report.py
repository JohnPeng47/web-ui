from pathlib import Path
import json
from collections import Counter
from enum import Enum
from typing import List, Union


# Compiles into one giant report

class VulnCategory(str, Enum):
    WEB_APP = "WEB_APP"
    API = "API"

class SeverityLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

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

def analyze_vulnerability_categories():
    reports_dir = Path("scrapers/reports")
    output_file = Path("analysis/HIGH_WEBAPP_ANALYSIS_NEW.txt")
    category_totals = Counter()
    
    # Track weakness counts for ALL HIGH severity reports
    high_severity_weaknesses = Counter()

    # Process all JSON files in the reports directory
    for report_file in reports_dir.glob("*.json"):
        with open(report_file, "r") as f:
            try:
                report = json.load(f)
                category = report.get("vuln_category")

                severity = map_severity_to_level(report.get("severity"))
                if severity != SeverityLevel.HIGH.value:
                    continue

                category_totals[category] += 1
                
                # Track weaknesses for ALL HIGH severity reports
                weakness = report.get("weaknesses", [])
                if weakness:  # If not empty array
                    high_severity_weaknesses[weakness[0]] += 1
            
            except json.JSONDecodeError:
                print(f"Error reading {report_file}")
                continue

    # Write results to file
    with open(output_file, "w") as f:
        f.write("\nWeakness Analysis for ALL HIGH Severity Reports\n")
        f.write("=" * 45 + "\n")
        
        if high_severity_weaknesses:
            total_weaknesses = sum(high_severity_weaknesses.values())
            f.write(f"\nTotal weaknesses found: {total_weaknesses}\n")
            f.write("-" * 35 + "\n")
            
            # Sort weaknesses by count in descending order
            for weakness, count in high_severity_weaknesses.most_common():
                percentage = (count / total_weaknesses * 100)
                f.write(f"{weakness}: {count:3} ({percentage:.1f}%)\n")
        else:
            f.write("\nNo weaknesses found in HIGH severity reports\n")

if __name__ == "__main__":
    analyze_vulnerability_categories()
