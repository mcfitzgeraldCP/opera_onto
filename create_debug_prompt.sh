#!/bin/bash

# Configuration
PROMPT_TEMPLATE="debug_prompt_template.md"
OUTPUT_FILE="debug_prompt.txt"
CODE_FILE="create_ontology.py"
LOG_FILE="Logs/log.txt"
SPEC_FILE="OPERA_ISA95_OWL_ONT_V5.csv"
SAMPLE_DATA_FILE="mx_toothpaste_finishing_sample_100lines.csv"

# Function to create the debug prompt
create_debug_prompt() {
    # Check if template exists
    if [ ! -f "$PROMPT_TEMPLATE" ]; then
        echo "Error: Template file $PROMPT_TEMPLATE not found"
        exit 1
    fi

    # Check if source code exists
    if [ ! -f "$CODE_FILE" ]; then
        echo "Error: $CODE_FILE not found"
        exit 1
    fi

    # Create output file using the template
    cp "$PROMPT_TEMPLATE" "$OUTPUT_FILE"

    # Replace placeholders with actual content
    # For ontology specification
    if [ -f "$SPEC_FILE" ]; then
        sed -i.bak "/<SPEC_CONTENT>/r $SPEC_FILE" "$OUTPUT_FILE"
        sed -i.bak "/<SPEC_CONTENT>/d" "$OUTPUT_FILE"
    else
        sed -i.bak "s/<SPEC_CONTENT>/Ontology specification file not found./" "$OUTPUT_FILE"
    fi

    # For sample data
    if [ -f "$SAMPLE_DATA_FILE" ]; then
        sed -i.bak "/<SAMPLE_CONTENT>/r $SAMPLE_DATA_FILE" "$OUTPUT_FILE"
        sed -i.bak "/<SAMPLE_CONTENT>/d" "$OUTPUT_FILE"
    else
        sed -i.bak "s/<SAMPLE_CONTENT>/Sample data file not found./" "$OUTPUT_FILE"
    fi

    # For code content
    if [ -f "$CODE_FILE" ]; then
        sed -i.bak "/<CODE_CONTENT>/r $CODE_FILE" "$OUTPUT_FILE"
        sed -i.bak "/<CODE_CONTENT>/d" "$OUTPUT_FILE"
    else
        sed -i.bak "s/<CODE_CONTENT>/Source code file not found./" "$OUTPUT_FILE"
    fi

    # For log content
    if [ -f "$LOG_FILE" ]; then
        sed -i.bak "/<LOG_CONTENT>/r $LOG_FILE" "$OUTPUT_FILE"
        sed -i.bak "/<LOG_CONTENT>/d" "$OUTPUT_FILE"
    else
        sed -i.bak "s/<LOG_CONTENT>/Log file not found./" "$OUTPUT_FILE"
    fi

    # Clean up backup files
    rm -f "$OUTPUT_FILE.bak"

    echo "Debug prompt created in $OUTPUT_FILE"
}

# Execute the function
create_debug_prompt 