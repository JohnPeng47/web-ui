from src.llm_models import openai_5

from src.detection.prompts import DetectAndSchedule
from src.agent.pages import Page, PageObservations
import json

model = openai_5()
page_contents = json.loads(open("agent_summary.json", "r").read())
page_observations = PageObservations.from_json(page_contents)

detect = DetectAndSchedule()
res = detect.invoke(model, prompt_args={"pages": page_observations})

for action in res:
    print(action.vulnerability_description)
    # print(action.page_item)
