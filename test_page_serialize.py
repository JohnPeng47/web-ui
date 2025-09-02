from src.agent.pages import Page, PageObservations
import json

page_contents = json.loads(open("agent_summary.json", "r").read())
page_observations = PageObservations.from_json(page_contents)

print(page_observations)