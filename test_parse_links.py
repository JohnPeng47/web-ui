from src.agent.links import parse_links_from_str

with open("login.html", "r") as f:
    content = f.read()
    for link in parse_links_from_str(content):
        print(link)