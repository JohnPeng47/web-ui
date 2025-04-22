from johnllm import LLMModel, LMP
from typing import List, Tuple
from pydantic import BaseModel
from enum import Enum
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from random import shuffle
import time

from .utils import process_reports_in_batches

class Level(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


# TODO: once labeled, run again with all examples
# to rank them in order of complexity
class InjectionClassifications(BaseModel):
    is_simple_injection: bool
    output_retrievable: bool
    

class CategorizeReports(LMP):
    prompt = """
{{report}}



"""
    response_format = InjectionClassifications

if __name__ == "__main__":
    process_reports_in_batches(
        Path("scrapers/high_reports"), 
        CategorizeReports, 
        model_name="deepseek-chat",
        batch_size=50, 
        max_workers=20
    )
