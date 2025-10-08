#!/bin/bash

# Find all files tracked by git
git ls-files | while IFS= read -r file; do
    # Search for TODO lines in each file
    grep -n "TODO" "$file" 2>/dev/null | while IFS=: read -r line_num content; do
        # Get the last commit date for this specific line
        commit_date=$(git log -1 --format="%ci" -L "${line_num},${line_num}:${file}" 2>/dev/null | head -1)
        
        # If we got a date, output the information
        if [ -n "$commit_date" ]; then
            echo "${commit_date}|${file}:${line_num}|${content}"
        fi
    done
done | sort -r | while IFS='|' read -r date location content; do
    # Format and display the results
    echo "[$date] $location"
    echo "  $content"
    echo ""
done