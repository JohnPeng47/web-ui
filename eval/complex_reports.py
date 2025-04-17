from opik import Opik
from opik import evaluate_prompt

import yaml
import json
from typing import Dict, Any
from src.llm import EXTRACT_REQUESTS_PROMPT, RequestResources
from eval.core import JohnLLMModel, parse_eval_args
from eval.scores import EqualsJSON

client = Opik()
client.delete_dataset("EXTRACT_PARAMS_DATASET")

EXTRACT_PARAMS_DATASET = client.create_dataset(name="EXTRACT_PARAMS_DATASET")
EXTRACT_PARAMS_DATASET.insert([
    {
        "report": """
@uzsunny reported that by creating two partner accounts sharing the same business email, it was possible to be granted "collaborator" access to any store without any merchant interaction.
We tracked down the bug to incorrect logic in a piece of code that was meant to automatically convert an existing normal user account into a collaborator account. The intention was that, when a partner already had a valid user account on the store, their collaborator account request could be accepted automatically, with the user account converted into a collaborator account.
The code did not properly check what type the existing account was, and therefore an existing collaborator account in the "pending" state (not yet accepted by the store owner) would be converted into an active collaborator account, effectively allowing the partner to approve their own request without interaction from the store owner.
    """    
    },   
])