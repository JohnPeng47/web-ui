import asyncio
import json
from playwright.async_api import async_playwright

from pydantic import BaseModel
from johnllm import LLMModel, LMP

class BurpLab(BaseModel):
    description: str
    hint: str
    solution: str

class CreateBurpLab(LMP):
    prompt = """
{{text}}

Separate the above into description, hint and solution
Note that each of the fields are sectioned into paragraph chunks
You need to correctly determine the paragraphs for:

description
hint
solution

In the above order according to the text
Now give your output
"""
    response_format = BurpLab

async def extract_text_from_div(url: str) -> tuple[str, str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url)

        # Wait for the specific div to be present
        await page.wait_for_selector("div.section.theme-white")

        # Extract all text content under the main div
        div_locator = page.locator("div.section.theme-white")
        
        # Get all text nodes within the main div, including those in nested elements
        main_content_text = await div_locator.evaluate_all("""
            elements => elements.map(el => {
                let text = '';
                const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
                let node;
                while(node = walker.nextNode()) {
                    text += node.textContent.trim() + ' ';
                }
                return text.trim();
            }).join('\\n\\n')
        """)
        
        # Extract text from p.widget-container-labelevel
        widget_locator = page.locator("p.widget-container-labelevel")
        widget_label_text = await widget_locator.evaluate_all("""
            elements => elements.map(el => {
                let text = '';
                const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
                let node;
                while(node = walker.nextNode()) {
                    text += node.textContent.trim() + ' ';
                }
                return text.trim();
            }).join('\\n\\n')
        """)
        
        # print("Extracted Text:")
        # print(main_content_text) # Was all_text_content

        await browser.close()
        return main_content_text, widget_label_text

async def build_lab_json(vuln_class, labs):
    DATA_DIR_PATH = Path("scripts/portswigger/data/server_side")
    LAB_JSON_PATH = DATA_DIR_PATH / (vuln_class + ".json")
    PORTSWIGGER_URL = "https://portswigger.net"

    output = []
    for link in labs:
        lab_dict = {}
        lab_dict["name"] = link["name"]
        lab_dict["link"] = link["link"]

        text, label = await extract_text_from_div(PORTSWIGGER_URL + link["link"])
        lab_info = CreateBurpLab().invoke(
            model=model,
            model_name="deepseek-chat",
            prompt_args={"text": text},
        )

        print("Creating lab json for: ", link["link"])
        print(lab_info)

        lab_dict["difficulty"] = label
        lab_dict["description"] = lab_info.description
        lab_dict["hint"] = lab_info.hint
        lab_dict["solution"] = lab_info.solution

        output.append(lab_dict)
    
    with open(LAB_JSON_PATH, "w") as f:
        json.dump(output, f, indent=4)

if __name__ == "__main__":
    from scripts.portswigger.data.server_side import SERVER_SIDE
    from pathlib import Path
    
    model = LLMModel()
    for vuln_class, labs in SERVER_SIDE.items():
        print("Building lab json for: ", vuln_class)

        asyncio.run(build_lab_json(vuln_class, labs))