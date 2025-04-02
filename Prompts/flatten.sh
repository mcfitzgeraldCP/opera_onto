#!/bin/bash

OUTPUT_FILE="ontology_generator_serialized.txt"
ROOT_DIR="ontology_generator"

# Clear output file if it exists
> "$OUTPUT_FILE"

# Find all files in the directory, excluding __pycache__ directories
find "$ROOT_DIR" -type f -not -path "*/\.*" -not -path "*/__pycache__/*" | sort | while read -r file; do
    # Create header showing the file path
    echo "===========================================" >> "$OUTPUT_FILE"
    echo "FILE: $file" >> "$OUTPUT_FILE"
    echo "===========================================" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Append file content
    cat "$file" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
done

echo "Serialization complete. Output saved to $OUTPUT_FILE"