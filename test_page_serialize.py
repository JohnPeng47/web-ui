from src.llm_models import openai_5

from src.agent.discovery.pages import Page, PageObservations
import json

model = openai_5()
page_contents = json.loads(open("tests/complete_page_data.json", "r").read())
page_observations = PageObservations.from_json(page_contents)

print(page_observations.get_page_item("3.4"))
# detect = DetectAndSchedule()
# res = detect.invoke(model, prompt_args={"pages": page_observations})

# for action in res:
#     print(action.vulnerability_description)
#     # print(action.page_item)
