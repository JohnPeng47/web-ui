import json
from collections import Counter, defaultdict

# Read the JSON data from the uploaded file
try:
    with open("osv/osv/Apache_Airflow_PyPI.json", "r") as f:
        content = f.read()
    
    # The content appears to be a partial JSON structure, let's try to parse what we can
    # Adding proper JSON structure to make it parseable
    
    data = json.loads(content)
    vulnerabilities = data.get("vulnerabilities", [])
    
    print(f"Found {len(vulnerabilities)} vulnerabilities")
    
    # Analyze Docker versions with CVEs
    docker_version_cve_count = Counter()
    docker_version_cves = defaultdict(list)
    
    ignored = 0
    for vuln in vulnerabilities:
        gh_matched = vuln["affected"][0].get("github_matched", None)
        if not gh_matched:
            continue
        if not gh_matched["gh_commit"] and not gh_matched["gh_pr"]:
            ignored += 1
            continue
        
        cve_id = (vuln["id"], vuln.get("summary", "Unknown"), vuln.get("vuln_categories"))
        affected_packages = vuln.get("affected", [])
        
        for package in affected_packages:
            docker_versions = package.get("docker_matched", [])
            for version in docker_versions:
                docker_version_cve_count[version] += 1
                docker_version_cves[version].append(cve_id)

    print(f"Ignored {ignored} vulnerabilities")
    print("\n=== VULNERABILITY ANALYSIS SUMMARY ===\n")
    
    # Docker versions with the greatest number of CVEs
    print("Docker versions with the greatest number of CVEs:")
    print("=" * 50)
    
    # Get top 20 versions with most CVEs
    top_versions = docker_version_cve_count.most_common(20)
    
    for i, (version, count) in enumerate(top_versions, 1):
        print(f"{i:2d}. {version:<20} - {count} CVE(s)")
    
    # Print CVEs for the top version
    if top_versions:
        top_version, top_count = top_versions[1]
        print(f"\nCVEs affecting the top version ({top_version}):")
        print("=" * 50)
        for cve in docker_version_cves[top_version]:
            print(f"  {cve}")
    
    # Additional statistics
    print(f"\nTotal unique Docker versions affected: {len(docker_version_cve_count)}")
    print(f"Total CVE instances across all versions: {sum(docker_version_cve_count.values())}")
    
except FileNotFoundError:
    print("Error: Could not find the paste.txt file")
except json.JSONDecodeError as e:
    print(f"Error parsing JSON: {e}")
    print("The file might not contain valid JSON data")
except Exception as e:
    print(f"An error occurred: {e}")