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
    DATA_DIR_PATH = Path("scripts/portswigger/data/client_side")
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
    from pathlib import Path

    XSS = {
        "cross_site_scripting": [
        {
            "index": 0,
            "link": "/web-security/cross-site-scripting/reflected/lab-html-context-nothing-encoded",
            "name": "Reflected XSS into HTML context with nothing encoded"
        },
        {
            "index": 1,
            "link": "/web-security/cross-site-scripting/stored/lab-html-context-nothing-encoded",
            "name": "Stored XSS into HTML context with nothing encoded"
        },
        {
            "index": 2,
            "link": "/web-security/cross-site-scripting/dom-based/lab-document-write-sink",
            "name": "DOM XSS in document.write sink using source location.search"
        },
        {
            "index": 3,
            "link": "/web-security/cross-site-scripting/dom-based/lab-innerhtml-sink",
            "name": "DOM XSS in innerHTML sink using source location.search"
        },
        {
            "index": 4,
            "link": "/web-security/cross-site-scripting/dom-based/lab-jquery-href-attribute-sink",
            "name": "DOM XSS in jQuery anchor href attribute sink using location.search source"
        },
        {
            "index": 5,
            "link": "/web-security/cross-site-scripting/dom-based/lab-jquery-selector-hash-change-event",
            "name": "DOM XSS in jQuery selector sink using a hashchange event"
        },
        {
            "index": 6,
            "link": "/web-security/cross-site-scripting/contexts/lab-attribute-angle-brackets-html-encoded",
            "name": "Reflected XSS into attribute with angle brackets HTML-encoded"
        },
        {
            "index": 7,
            "link": "/web-security/cross-site-scripting/contexts/lab-href-attribute-double-quotes-html-encoded",
            "name": "Stored XSS into anchor href attribute with double quotes HTML-encoded"
        },
        {
            "index": 8,
            "link": "/web-security/cross-site-scripting/contexts/lab-javascript-string-angle-brackets-html-encoded",
            "name": "Reflected XSS into a JavaScript string with angle brackets HTML encoded"
        },
        {
            "index": 9,
            "link": "/web-security/cross-site-scripting/dom-based/lab-document-write-sink-inside-select-element",
            "name": "DOM XSS in document.write sink using source location.search inside a select element"
        },
        {
            "index": 10,
            "link": "/web-security/cross-site-scripting/dom-based/lab-angularjs-expression",
            "name": "DOM XSS in AngularJS expression with angle brackets and double quotes HTML-encoded"
        },
        {
            "index": 11,
            "link": "/web-security/cross-site-scripting/dom-based/lab-dom-xss-reflected",
            "name": "Reflected DOM XSS"
        },
        {
            "index": 12,
            "link": "/web-security/cross-site-scripting/dom-based/lab-dom-xss-stored",
            "name": "Stored DOM XSS"
        },
        {
            "index": 13,
            "link": "/web-security/cross-site-scripting/contexts/lab-html-context-with-most-tags-and-attributes-blocked",
            "name": "Reflected XSS into HTML context with most tags and attributes blocked"
        },
        {
            "index": 14,
            "link": "/web-security/cross-site-scripting/contexts/lab-html-context-with-all-standard-tags-blocked",
            "name": "Reflected XSS into HTML context with all tags blocked except custom ones"
        },
        {
            "index": 15,
            "link": "/web-security/cross-site-scripting/contexts/lab-some-svg-markup-allowed",
            "name": "Reflected XSS with some SVG markup allowed"
        },
        {
            "index": 16,
            "link": "/web-security/cross-site-scripting/contexts/lab-canonical-link-tag",
            "name": "Reflected XSS in canonical link tag"
        },
        {
            "index": 17,
            "link": "/web-security/cross-site-scripting/contexts/lab-javascript-string-single-quote-backslash-escaped",
            "name": "Reflected XSS into a JavaScript string with single quote and backslash escaped"
        },
        {
            "index": 18,
            "link": "/web-security/cross-site-scripting/contexts/lab-javascript-string-angle-brackets-double-quotes-encoded-single-quotes-escaped",
            "name": "Reflected XSS into a JavaScript string with angle brackets and double quotes HTML-encoded and single quotes escaped"
        },
        {
            "index": 19,
            "link": "/web-security/cross-site-scripting/contexts/lab-onclick-event-angle-brackets-double-quotes-html-encoded-single-quotes-backslash-escaped",
            "name": "Stored XSS into onclick event with angle brackets and double quotes HTML-encoded and single quotes and backslash escaped"
        },
        {
            "index": 20,
            "link": "/web-security/cross-site-scripting/contexts/lab-javascript-template-literal-angle-brackets-single-double-quotes-backslash-backticks-escaped",
            "name": "Reflected XSS into a template literal with angle brackets, single, double quotes, backslash and backticks Unicode-escaped"
        },
        {
            "index": 21,
            "link": "/web-security/cross-site-scripting/exploiting/lab-stealing-cookies",
            "name": "Exploiting cross-site scripting to steal cookies"
        },
        {
            "index": 22,
            "link": "/web-security/cross-site-scripting/exploiting/lab-capturing-passwords",
            "name": "Exploiting cross-site scripting to capture passwords"
        },
        {
            "index": 23,
            "link": "/web-security/cross-site-scripting/exploiting/lab-perform-csrf",
            "name": "Exploiting XSS to bypass CSRF defenses"
        },
        {
            "index": 24,
            "link": "/web-security/cross-site-scripting/contexts/client-side-template-injection/lab-angular-sandbox-escape-without-strings",
            "name": "Reflected XSS with AngularJS sandbox escape without strings"
        },
        {
            "index": 25,
            "link": "/web-security/cross-site-scripting/contexts/client-side-template-injection/lab-angular-sandbox-escape-and-csp",
            "name": "Reflected XSS with AngularJS sandbox escape and CSP"
        },
        {
            "index": 26,
            "link": "/web-security/cross-site-scripting/contexts/lab-event-handlers-and-href-attributes-blocked",
            "name": "Reflected XSS with event handlers and href attributes blocked"
        },
        {
            "index": 27,
            "link": "/web-security/cross-site-scripting/contexts/lab-javascript-url-some-characters-blocked",
            "name": "Reflected XSS in a JavaScript URL with some characters blocked"
        },
        {
            "index": 28,
            "link": "/web-security/cross-site-scripting/content-security-policy/lab-very-strict-csp-with-dangling-markup-attack",
            "name": "Reflected XSS protected by very strict CSP, with dangling markup attack"
        },
        {
            "index": 29,
            "link": "/web-security/cross-site-scripting/content-security-policy/lab-csp-bypass",
            "name": "Reflected XSS protected by CSP, with CSP bypass"
        }
    ]
    }
    
    model = LLMModel()
    for vuln_class, labs in XSS.items():
        print("Building lab json for: ", vuln_class)

        asyncio.run(build_lab_json(vuln_class, labs))