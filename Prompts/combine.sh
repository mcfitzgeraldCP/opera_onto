#!/bin/bash

# Check if correct number of arguments are provided
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <ontology_file> <data_sample_file> <source_code_file>"
    exit 1
fi

# Assign arguments to variables
ontology_file=$1
data_sample_file=$2
source_code_file=$3
output_file="combined_input.txt"

# Check if all input files exist
for file in "$ontology_file" "$data_sample_file" "$source_code_file"; do
    if [ ! -f "$file" ]; then
        echo "Error: File '$file' does not exist!"
        exit 1
    fi
done

# Create the combined file with sections
{
    echo "=== ONTOLOGY SPECIFICATION (csv) ==="
    echo
    cat "$ontology_file"
    echo
    echo "=== DATA SAMPLE (csv)==="
    echo
    cat "$data_sample_file"
    echo
    echo "=== SOURCE CODE (python)==="
    echo
    cat "$source_code_file"
} > "$output_file"

echo "Combined file created successfully as '$output_file'"