#!/bin/bash

# Bash script to run start_single_task_agent.py 10 times
# Usage: ./run_agent_10_times.sh

# Set the output directory
OUTPUT_DIR="agent_outputs"
mkdir -p "$OUTPUT_DIR"

# Get current timestamp for unique run identifier
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "Starting 10 runs of start_single_task_agent.py..."
echo "Output files will be saved to: $OUTPUT_DIR"

# Run the script 10 times
for i in {1..10}; do
    echo "Running iteration $i/10..."
    
    # Create unique output filename
    OUTPUT_FILE="$OUTPUT_DIR/agent_run_${TIMESTAMP}_${i}.json"
    
    # Run the Python script with the output file path
    python start_single_task_agent.py "$OUTPUT_FILE"
    
    if [ $? -eq 0 ]; then
        echo "  ✅ Iteration $i completed successfully"
    else
        echo "  ❌ Iteration $i failed"
    fi
    
    # Add a small delay between runs
    sleep 2
done

echo "All 10 runs completed!"
echo "Results saved in: $OUTPUT_DIR"
