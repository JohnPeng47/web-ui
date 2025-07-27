#!/bin/bash

# OSV Batch Scanner
# Reads search terms from a list and runs OSV vulnerability searches for each term

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Configuration
SEARCH_TERMS_FILE="${1:-search_terms.txt}"
OSV_SCRIPT="${2:-osv_scanner.py}"
OUTPUT_DIR="osv"
ECOSYSTEM="${ECOSYSTEM:-}"  # Default ecosystem (can be set via environment variable)
VERSION="${VERSION:-}"      # Default version (can be set via environment variable)
COMMIT="${COMMIT:-}"        # Default commit (can be set via environment variable)
MAX_CANDIDATES="${MAX_CANDIDATES:-10}"  # Maximum candidate mappings

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] ${message}${NC}"
}

# Function to sanitize filename (remove special characters)
sanitize_filename() {
    local input="$1"
    # Replace problematic characters with underscores
    echo "$input" | sed 's/[^a-zA-Z0-9._-]/_/g' | sed 's/__*/_/g' | sed 's/^_\|_$//g'
}

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [search_terms_file] [osv_script]

Options:
    search_terms_file   File containing search terms (default: search_terms.txt)
    osv_script         Path to OSV scanner script (default: osv_scanner.py)

Environment Variables:
    ECOSYSTEM          Default ecosystem (e.g., Go, npm, PyPI)
    VERSION           Default version string
    COMMIT            Default commit hash
    MAX_CANDIDATES    Maximum candidate mappings (default: 10)

Examples:
    $0                                    # Use defaults
    $0 my_terms.txt my_scanner.py        # Custom files
    ECOSYSTEM=Go $0                      # Set default ecosystem
    ECOSYSTEM=npm VERSION=1.0.0 $0       # Set ecosystem and version

Search terms file format:
    # Lines starting with # are comments
    mattermost
    github.com/mattermost/mattermost-server
    package:ecosystem:version            # Specify ecosystem and version
    package::version                     # Specify version only
    package:ecosystem                    # Specify ecosystem only
EOF
}

# Check if help is requested
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

# Validate inputs
if [[ ! -f "$SEARCH_TERMS_FILE" ]]; then
    print_status "$RED" "Error: Search terms file '$SEARCH_TERMS_FILE' not found!"
    print_status "$YELLOW" "Create a file with one search term per line, e.g.:"
    cat << EOF
mattermost
github.com/mattermost/mattermost-server
kubernetes
github.com/kubernetes/kubernetes
EOF
    exit 1
fi

if [[ ! -f "$OSV_SCRIPT" ]]; then
    print_status "$RED" "Error: OSV scanner script '$OSV_SCRIPT' not found!"
    print_status "$YELLOW" "Make sure the Python script exists and is executable."
    exit 1
fi

# Check if Python script is executable
if [[ ! -x "$OSV_SCRIPT" ]]; then
    print_status "$YELLOW" "Making OSV script executable..."
    chmod +x "$OSV_SCRIPT"
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"
print_status "$BLUE" "Created output directory: $OUTPUT_DIR"

# Read search terms and count total
mapfile -t search_terms < <(grep -v '^#' "$SEARCH_TERMS_FILE" | grep -v '^[[:space:]]*$')
total_terms=${#search_terms[@]}

if [[ $total_terms -eq 0 ]]; then
    print_status "$RED" "Error: No search terms found in '$SEARCH_TERMS_FILE'"
    exit 1
fi

print_status "$GREEN" "Found $total_terms search terms to process"
print_status "$BLUE" "Starting batch vulnerability scan..."

# Initialize counters
success_count=0
error_count=0
start_time=$(date +%s)

# Process each search term
for i in "${!search_terms[@]}"; do
    term="${search_terms[$i]}"
    current=$((i + 1))
    
    # Parse term for ecosystem and version info
    # Format: package:ecosystem:version or package:ecosystem or package::version
    IFS=':' read -ra PARTS <<< "$term"
    package_name="${PARTS[0]}"
    term_ecosystem="${PARTS[1]:-$ECOSYSTEM}"
    term_version="${PARTS[2]:-$VERSION}"
    
    # Skip empty package names
    if [[ -z "$package_name" ]]; then
        print_status "$YELLOW" "[$current/$total_terms] Skipping empty package name"
        continue
    fi
    
    # Create safe filename
    safe_filename=$(sanitize_filename "$package_name")
    if [[ -n "$term_ecosystem" ]]; then
        safe_filename="${safe_filename}_${term_ecosystem}"
    fi
    if [[ -n "$term_version" ]]; then
        safe_filename="${safe_filename}_$(sanitize_filename "$term_version")"
    fi
    output_file="$OUTPUT_DIR/${safe_filename}.txt"
    
    print_status "$BLUE" "[$current/$total_terms] Processing: $package_name"
    if [[ -n "$term_ecosystem" ]]; then
        print_status "$BLUE" "  Ecosystem: $term_ecosystem"
    fi
    if [[ -n "$term_version" ]]; then
        print_status "$BLUE" "  Version: $term_version"
    fi
    
    # Build command arguments
    cmd_args=("$package_name")
    
    if [[ -n "$term_ecosystem" ]]; then
        cmd_args+=(--ecosystem "$term_ecosystem")
    fi
    
    if [[ -n "$term_version" ]]; then
        cmd_args+=(--version "$term_version")
    fi
    
    if [[ -n "$COMMIT" ]]; then
        cmd_args+=(--commit "$COMMIT")
    fi
    
    cmd_args+=(--max-candidates "$MAX_CANDIDATES")
    
    # Run the OSV scanner and capture output
    print_status "$YELLOW" "  Running: python3 $OSV_SCRIPT ${cmd_args[*]}"
    
    if python3 "$OSV_SCRIPT" "${cmd_args[@]}" > "$output_file" 2>&1; then
        # Check if any vulnerabilities were found
        if grep -q "Found.*vulnerability" "$output_file" || grep -q "VULNERABILITY:" "$output_file"; then
            vuln_count=$(grep -c "VULNERABILITY:" "$output_file" || echo "0")
            print_status "$RED" "  ⚠️  Found $vuln_count vulnerability(ies) → $output_file"
        else
            print_status "$GREEN" "  ✅ No vulnerabilities found → $output_file"
        fi
        ((success_count++))
    else
        print_status "$RED" "  ❌ Error occurred → $output_file"
        echo "Error processing $package_name on $(date)" >> "$output_file"
        ((error_count++))
    fi
    
    # Add separator and small delay to avoid rate limiting
    echo "" >> "$output_file"
    sleep 0.5
done

# Calculate execution time
end_time=$(date +%s)
execution_time=$((end_time - start_time))

# Summary
print_status "$GREEN" "=========================================="
print_status "$GREEN" "Batch scan completed!"
print_status "$GREEN" "Total terms processed: $total_terms"
print_status "$GREEN" "Successful scans: $success_count"
if [[ $error_count -gt 0 ]]; then
    print_status "$RED" "Failed scans: $error_count"
fi
print_status "$GREEN" "Execution time: ${execution_time}s"
print_status "$GREEN" "Results saved in: $OUTPUT_DIR/"

# Show summary of files with vulnerabilities
print_status "$BLUE" "Files with vulnerabilities found:"
vulnerability_files=()
while IFS= read -r -d '' file; do
    if grep -q "VULNERABILITY:" "$file" 2>/dev/null; then
        vuln_count=$(grep -c "VULNERABILITY:" "$file")
        basename_file=$(basename "$file")
        print_status "$RED" "  $basename_file ($vuln_count vulnerabilities)"
        vulnerability_files+=("$file")
    fi
done < <(find "$OUTPUT_DIR" -name "*.txt" -print0)

if [[ ${#vulnerability_files[@]} -eq 0 ]]; then
    print_status "$GREEN" "  🎉 No vulnerabilities found in any packages!"
fi

# Optional: Create summary report
summary_file="$OUTPUT_DIR/scan_summary_$(date +%Y%m%d_%H%M%S).txt"
{
    echo "OSV Batch Scan Summary"
    echo "======================"
    echo "Date: $(date)"
    echo "Total packages scanned: $total_terms"
    echo "Successful scans: $success_count"
    echo "Failed scans: $error_count"
    echo "Execution time: ${execution_time}s"
    echo ""
    echo "Packages with vulnerabilities:"
    for file in "${vulnerability_files[@]}"; do
        vuln_count=$(grep -c "VULNERABILITY:" "$file")
        echo "  $(basename "$file" .txt): $vuln_count vulnerabilities"
    done
} > "$summary_file"

print_status "$BLUE" "Summary report saved: $summary_file"
print_status "$GREEN" "Done! 🎯"