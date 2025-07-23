from opik import Opik
from opik import evaluate_prompt

import yaml
import json
from typing import Dict, Any
from src.llm import EXTRACT_REQUESTS_PROMPT, RequestResources
from eval.core import JohnLLMModel, parse_eval_args
from eval.scores import EqualsJSON

client = Opik()
# client.delete_dataset("EXTRACT_PARAMS_DATASET")

# EXTRACT_PARAMS_DATASET = client.create_dataset(name="EXTRACT_PARAMS_DATASET")
# EXTRACT_PARAMS_DATASET.insert([
#     {
#         "request": """
# GET http://localhost:8000/inventory/list/
#     """,
#         "name": "Empty GET",
#         "expected_output": json.dumps({
#             "resources": [],
#         })
#     },   
#     {
#         "request": """
# POST http://localhost:8000/orders/4/add-items/
# {'csrfmiddlewaretoken': 'tIF5b1nxroHGIreJaoC5vXsisnO3yWiYxLGIJ0pcAI6puVhSEkAtXCB8dWIAWoVs', 'items-TOTAL_FORMS': '1', 'items-INITIAL_FORMS': '0', 'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000', 'items-0-product': '', 'items-0-variant': '', 'items-0-quantity': '1', 'items-0-price': ''}
#     """,
#         "name": "URL param POST",
#         "expected_output": json.dumps({
#         "resources": [
#             {
#                 "id": "4",
#                 "type": {
#                     "name": "order",
#                     "requests": []
#                 },
#                 "request_part": "URL",
#                 "selected_slice": {
#                     "URL": "/orders/$%&4$%&/add-items/"
#                 }
#             }
#         ]
#     })
#     },
#     {
#         "request": """
# POST http://localhost:8000/inventory/create/
# {'csrfmiddlewaretoken': 'h0EclP8OYE80II6kTnXGYgTqiyFPhTBxl3FPTOat7YxJuc9tnjV4qV2g37zmFle1', 'product': '2', 'variant': '', 'quantity': '11', 'transaction_type': 'received', 'reference': '1', 'notes': 'sg'}
# """,
#         "name": "POST param body",
#         "expected_output": json.dumps({
#             "resources": [
#                 {
#                     "id": "2",
#                     "type": {
#                         "name": "product",
#                         "requests": []
#                     },
#                     "request_part": "BODY",
#                     "selected_slice": {
#                         "BODY": "product"
#                     }
#                 }
#             ]
#         })
#     },
#     {
#         "request": """
# POST http://localhost:8000/orders/create/
# {'csrfmiddlewaretoken': 'HWNMVs9AWYLw3tuOYbbYPsoPTEUCX1YBLZOptrbf5iafPXxXs79mh7xFEdO9ltB5', 'customer': '3', 'shipping_address': 'EG', 'billing_address': 'WWGE', 'notes': 'GWGE'}
#         """,
#         "name": "Customer ID in POST body",
#         "expected_output": json.dumps({
#             "resources": [
#                 {
#                     "id": "3",
#                     "request_part": "BODY",
#                     "type": {
#                         "name": "customer",
#                         "requests": []
#                     },
#                     "selected_slice": {
#                         "BODY": "customer"
#                     }
#                 }
#             ]
#         })
#     }
# ])


def convert_to_json(request_info: RequestResources, expected_out) -> Dict[str, Any]:
    # TODO: implement this as decorator
    return {
        "output": request_info.model_dump(),
        "reference": yaml.safe_load(expected_out)
    }

if __name__ == "__main__":
    EXTRACT_PARAMS_DATASET = client.get_dataset("EXTRACT_PARAMS_DATASET")
    experiment_name, project_name = parse_eval_args(EXTRACT_REQUESTS_PROMPT, response_format=RequestResources)
    evaluate_prompt(
        messages = [
            {
                "content": EXTRACT_REQUESTS_PROMPT,
                "role": "user",
            },
        ],
        dataset=EXTRACT_PARAMS_DATASET, 
        model=JohnLLMModel(model_name="gpt-4o", response_format=RequestResources),
        eval_fn= convert_to_json,
        scoring_metrics=[
            EqualsJSON(exclude_fields=["description"], only_expected_keys=True)
        ],
        experiment_name=experiment_name,
        # project_name=project_name
    )