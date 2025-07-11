from pathlib import Path
import tiktoken
from enum import Enum, auto
from typing import List

from src.llm_provider import LMP
from src.llm_models import gemini_25_flash, openai_4o   
from pydantic import BaseModel


LOG_DIR = Path("logs/xss_agent")


class AgentObservations(BaseModel):
    categories: List[str]


class ClassifyAgentSteps(LMP):
    prompt = """
<log_content>
{{log_content}}
</log_content>


You are given a log file containing traces of a pentesting agent
Your job is to come up with a set of categories for the agent's steps/actions observed from the above

Here are some categories to get you started: 
class ActionType(Enum):
    # ── Recon / discovery ──────────────────────────────────────────
    INITIAL_RECON      = auto()   # First blind GET to learn page skeleton
    PARAM_PROBE        = auto()   # Append a marker to a query/form field
    REFLECTION_SCAN    = auto()   # Search response for the marker
    CONTEXT_INSPECT    = auto()   # Dump surrounding HTML / inline JS
    ENV_CHECK          = auto()   # Check CSP, headers, framework libs, etc.

    # ── Exploit development ────────────────────────────────────────
    PAYLOAD_CRAFT      = auto()   # Build or refine an XSS payload
    PAYLOAD_DELIVER    = auto()   # Fire the payload via GET/POST
    STORED_POST        = auto()   # Submit payload through a comment / form
    EXEC_VERIFY        = auto()   # Confirm code-exec (e.g., browser_check_xss)

    # ── Control-flow / meta actions ────────────────────────────────
    ERROR_FIX          = auto()   # Repair a code bug (NameError, import, etc.)
    HOST_SWITCH        = auto()   # Change to a new lab hostname
    LOOP_REPEAT        = auto()   # Re-run essentially the same probe without new insight

Feel free to create a more fitting category for a step if you think the above doesn't fit
Ignore any steps that are not related to the agent's actions
Also ignore instructions to critique the steps that are sometimes apart of <log_contents>

Give your output as a list of categories
"""
    response_format = AgentObservations


def process_xss_agent_steps(log_dir: Path):
    log_files = list(log_dir.glob("**/concat_agent_logs.log"))
    encoding = tiktoken.get_encoding("cl100k_base")
    total_tokens = 0
    results = []
    
    for log_file in log_files:
        with open(log_file, "r", encoding="utf-8") as f:
            log_content = f.read()
            tokens = len(encoding.encode(log_content))
            if tokens > 100000:
                continue

            total_tokens += tokens
            results.append((log_content, tokens))
            print(f"{log_file}: {len(log_content)} chars, {tokens} tokens")
    
    print(f"Total tokens across all log files: {total_tokens}")
    return results
        
if __name__ == "__main__":
    for file, tokens in process_xss_agent_steps(LOG_DIR):
        if tokens > 100000:
            continue
        
        action = ClassifyAgentSteps()
        res = action.invoke(
            model=openai_4o(),
            prompt_args={"log_content": file}
        )
        print(res)
        break