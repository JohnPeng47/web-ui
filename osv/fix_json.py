from pathlib import Path
import json
from .docker import iter_all_tags

if __name__ == "__main__":
    for file in Path("osv/osv").glob("*.json"):
        with open(file, "r") as f:
            data = json.load(f)


        print(data["docker_repo"])
        docker_tags = set(iter_all_tags(data["docker_repo"]))
        for vuln in data["vulnerabilities"]:
            for affected in vuln["affected"]:
                prev_matched = affected["docker_matched"]
                affected["docker_matched"] = [tag for tag in prev_matched if tag in docker_tags]
                # print(len(affected["docker_matched"]) - len(prev_matched))
                # print(affected["docker_matched"])
        
        with open(file, "w") as f:
            json.dump(data, f, indent=4)
        
        print("Fixed file: ", file)