from pathlib import Path
import json
from enum import Enum
import shutil

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


def collect_high_webapp_reports(reports_dir: Path, output_dir: Path):
    """Move HIGH severity WEB_APP vulnerability reports to output directory
    
    Args:
        reports_dir: Directory containing report JSON files
        output_dir: Directory to move high severity reports to
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    moved_count = 0
    for report_file in reports_dir.glob("*.json"):
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                report = json.load(f)

            print(report_file, map_severity_to_level(report.get("severity")))
            if (map_severity_to_level(report.get("severity")) == SeverityLevel.HIGH.value):
                shutil.copy2(report_file, output_dir / report_file.name)
                moved_count += 1
                
        except json.JSONDecodeError:
            print(f"Error reading {report_file}")
            continue
    
    print(f"Moved {moved_count} HIGH severity reports")
    print(f"HIGH severity WEB_APP reports have been copied to {output_dir}")

if __name__ == "__main__":
    reports_dir = Path("scrapers/reports")
    output_dir = Path("scrapers/high_reports")
    collect_high_webapp_reports(reports_dir, output_dir)
