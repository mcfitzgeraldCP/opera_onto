#!/bin/bash

# Filter unique warnings from Python log file
# Usage: ./filter_warnings.sh <logfile>

if [ $# -ne 1 ]; then
    echo "Usage: $0 <logfile>"
    exit 1
fi

# Check if input file exists
if [ ! -f "$1" ]; then
    echo "Error: File '$1' not found"
    exit 1
fi

# Extract WARNING messages, remove timestamps, and get unique entries
# The awk command removes the timestamp and log level prefix
# sort -u ensures we only get unique messages
grep "WARNING" "$1" | \
    awk -F " - " '{$1=""; print substr($0,2)}' | \
    sort -u
