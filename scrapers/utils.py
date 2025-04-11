from pathlib import Path
import json
from collections import Counter
from enum import Enum
from typing import List, Union


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
