import json
import os
from pathlib import Path


def clean_vulnerability(vuln):
    """
    Clean a single vulnerability entry to only include required fields.
    Returns None if no github commit exists.
    """
    # Check if any affected package has github_matched.gh_commit = true
    has_github_commit = False
    docker_matched = []
    
    for affected in vuln.get("affected", []):
        github_matched = affected.get("github_matched", {})
        if github_matched.get("gh_commit", False):
            has_github_commit = True
        
        # Collect docker_matched data
        # if "docker_matched" in affected:
        #     docker_matched.extend(affected["docker_matched"])
    
    # Skip if no github commit
    if not has_github_commit:
        return None
    
    # Extract github commit URLs from references
    github_commit_urls = []
    for reference in vuln.get("references", []):
        url = reference.get("url", "")
        if "github.com" in url and "/commit/" in url:
            github_commit_urls.append(url)
    
    # Extract required fields
    cleaned_vuln = {
        "id": vuln.get("id"),
        "summary": vuln.get("summary"),
        "details": vuln.get("details"),
        "github_commit_urls": github_commit_urls,
        "vuln_categories": vuln.get("vuln_categories", []),
        "docker_matched": docker_matched,
    }
    
    return cleaned_vuln


def clean_json_file(input_path, output_path):
    """
    Clean a single JSON file and save the cleaned version.
    Returns the number of vulnerabilities processed.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    vulnerabilities = data.get("vulnerabilities", [])
    cleaned_vulns = []
    
    for vuln in vulnerabilities:
        cleaned_vuln = clean_vulnerability(vuln)
        if cleaned_vuln:
            cleaned_vulns.append(cleaned_vuln)
    
    # Create cleaned data structure
    cleaned_data = {
        "subject": data.get("subject"),
        "total_vulnerabilities": len(cleaned_vulns),
        "vulnerabilities": cleaned_vulns
    }
    
    # Write cleaned data to output file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
    
    return len(cleaned_vulns)


def clean_json_folder(input_folder, output_folder):
    """
    Clean all JSON files in the input folder and save to output folder.
    """
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    total_vulns = 0
    processed_files = 0
    
    # Process all JSON files in the input folder
    for json_file in input_path.glob("*.json"):
        output_file = output_path / json_file.name
        
        try:
            vuln_count = clean_json_file(json_file, output_file)
            total_vulns += vuln_count
            processed_files += 1
            print(f"Processed {json_file.name}: {vuln_count} vulnerabilities with GitHub commits")
        except Exception as e:
            print(f"Error processing {json_file.name}: {e}")
    
    print(f"\nSummary:")
    print(f"Files processed: {processed_files}")
    print(f"Total vulnerabilities with GitHub commits: {total_vulns}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python clean_json.py <input_folder> <output_folder>")
        sys.exit(1)
    
    input_folder = sys.argv[1]
    output_folder = sys.argv[2]
    
    if not os.path.exists(input_folder):
        print(f"Error: Input folder '{input_folder}' does not exist")
        sys.exit(1)
    
    clean_json_folder(input_folder, output_folder)
