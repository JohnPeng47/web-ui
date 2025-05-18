#!/usr/bin/env python3

import re
import os
from playwright.sync_api import sync_playwright

def extract_lab_links(url):
    """
    Visit the given URL and extract all links that match the lab pattern
    """
    with sync_playwright() as p:
        # Use a persistent context with the specified user profile
        user_data_dir = os.path.abspath("tmp/profiles/john")
        os.makedirs(user_data_dir, exist_ok=True)
        
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True  # Set to True for headless mode
        )
        
        page = browser.new_page()
        print(f"Navigating to {url}")
        page.goto(url)
        
        # Wait for the content to load
        page.wait_for_load_state("networkidle")
        
        # Get all links on the page
        links = page.eval_on_selector_all("a[href]", """elements => {
            return elements.map(element => element.href);
        }""")
        
        # Filter for lab links
        lab_pattern = r"/web-security/[^/]+/lab-"
        lab_links = [link for link in links if re.search(lab_pattern, link)]
        
        browser.close()
        
        return lab_links

def extract_subpage_links(url):
    """
    Visit the given URL and extract all links that match the subpage pattern
    """
    with sync_playwright() as p:
        user_data_dir = os.path.abspath("tmp/profiles/john")
        os.makedirs(user_data_dir, exist_ok=True)
        
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False
        )
        
        page = browser.new_page()
        print(f"Navigating to {url}")
        page.goto(url)
        
        page.wait_for_load_state("networkidle")
        
        links = page.eval_on_selector_all("a[href]", """elements => {
            return elements.map(element => element.href);
        }""")
        
        # Filter for subpage links (those containing #)
        subpage_pattern = r"/web-security/[^/]+#[^/]+$"
        subpage_links = [link for link in links if re.search(subpage_pattern, link)]
        
        browser.close()
        
        return subpage_links

def main():
    all_lab_links = set()  # Use a set to avoid duplicates
    
    with open("scripts/portswigger_excersises/labs.txt", "r") as file:
        for line in file:
            if line.strip().startswith("https://"):
                base_url = line.strip()
                print(f"\nProcessing base URL: {base_url}")
                
                # Get lab links from the base URL
                base_lab_links = extract_lab_links(base_url)
                all_lab_links.update(base_lab_links)
                
                # Get subpage links
                subpage_links = extract_subpage_links(base_url)
                print(f"Found {len(subpage_links)} subpages")
                
                # Process each subpage
                for subpage in subpage_links:
                    print(f"\nProcessing subpage: {subpage}")
                    subpage_lab_links = extract_lab_links(subpage)
                    all_lab_links.update(subpage_lab_links)
                    
                break
    
    print(f"\nFound {len(all_lab_links)} total unique lab links:")
    for link in filter(lambda x: "sql-injection" in x, sorted(all_lab_links)):
        print(link)

if __name__ == "__main__":
    main()
