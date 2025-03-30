#!/bin/bash

# Show usage if no arguments provided
usage() {
    echo "Usage: $0 <code_file> <spec_file> <data_file>"
    echo "Example: $0 create_ontology.py OPERA_ISA95_OWL_ONT_V6.csv mx_toothpaste_finishing_sample_100lines.csv"
    echo ""
    echo "Arguments:"
    echo "  code_file  : Path to the source code file (e.g., create_ontology.py)"
    echo "  spec_file  : Path to the ontology specification file (e.g., OPERA_ISA95_OWL_ONT_V6.csv)"
    echo "  data_file  : Path to the sample data file (e.g., mx_toothpaste_finishing_sample_100lines.csv)"
    exit 1
}

# Check if we have the required number of arguments
if [ "$#" -ne 3 ]; then
    usage
fi

# Configuration
PROMPT_TEMPLATE="debug_prompt_template.md"
OUTPUT_FILE="debug_prompt.txt"
CODE_FILE="$1"
SPEC_FILE="$2"
SAMPLE_DATA_FILE="$3"
LOG_FILE="Logs/log.txt"

# Function to create the debug prompt
create_debug_prompt() {
    # Check if all required files exist
    for file in "$PROMPT_TEMPLATE" "$CODE_FILE" "$SPEC_FILE" "$SAMPLE_DATA_FILE"; do
        if [ ! -f "$file" ]; then
            echo "Error: Required file not found: $file"
            usage
        fi
    done

    # Create output file using the template
    cp "$PROMPT_TEMPLATE" "$OUTPUT_FILE"

    # Replace placeholders with actual content
    # For ontology specification
    sed -i.bak "/<SPEC_CONTENT>/r $SPEC_FILE" "$OUTPUT_FILE"
    sed -i.bak "/<SPEC_CONTENT>/d" "$OUTPUT_FILE"

    # For sample data
    sed -i.bak "/<SAMPLE_CONTENT>/r $SAMPLE_DATA_FILE" "$OUTPUT_FILE"
    sed -i.bak "/<SAMPLE_CONTENT>/d" "$OUTPUT_FILE"

    # For code content
    sed -i.bak "/<CODE_CONTENT>/r $CODE_FILE" "$OUTPUT_FILE"
    sed -i.bak "/<CODE_CONTENT>/d" "$OUTPUT_FILE"

    # For log content (optional)
    if [ -f "$LOG_FILE" ]; then
        sed -i.bak "/<LOG_CONTENT>/r $LOG_FILE" "$OUTPUT_FILE"
        sed -i.bak "/<LOG_CONTENT>/d" "$OUTPUT_FILE"
    else
        sed -i.bak "s/<LOG_CONTENT>/Log file not found./" "$OUTPUT_FILE"
    fi

    # Clean up backup files
    rm -f "$OUTPUT_FILE.bak"

    echo "Debug prompt created in $OUTPUT_FILE"
    echo "Using:"
    echo "  Code file: $CODE_FILE"
    echo "  Spec file: $SPEC_FILE"
    echo "  Data file: $SAMPLE_DATA_FILE"
}

# Execute the function
create_debug_prompt 