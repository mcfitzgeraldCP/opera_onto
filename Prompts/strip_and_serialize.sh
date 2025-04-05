#!/bin/bash

OUTPUT_FILE="ontology_generator_minimal.txt"
ROOT_DIR="ontology_generator"

# Clear output file if it exists
> "$OUTPUT_FILE"

# Function to strip comments and docstrings from Python code
strip_python_code() {
    # Use Python to strip comments and docstrings
    python3 -c "
import ast
import sys

def strip_docstrings(node):
    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
        node.body = [n for n in node.body if not isinstance(n, ast.Expr) or not isinstance(n.value, ast.Constant) or not isinstance(n.value.value, str)]
    for child in ast.iter_child_nodes(node):
        strip_docstrings(child)
    return node

def strip_comments_and_docstrings(source):
    # Parse the source code
    tree = ast.parse(source)
    # Strip docstrings
    tree = strip_docstrings(tree)
    # Convert back to source code
    return ast.unparse(tree)

# Read input from stdin
source = sys.stdin.read()
# Process the code
result = strip_comments_and_docstrings(source)
# Print the result
print(result)
"
}

# Find all Python files in the directory, excluding __pycache__ directories
find "$ROOT_DIR" -type f -name "*.py" -not -path "*/\.*" -not -path "*/__pycache__/*" | sort | while read -r file; do
    # Create header showing the file path
    echo "===========================================" >> "$OUTPUT_FILE"
    echo "FILE: $file" >> "$OUTPUT_FILE"
    echo "===========================================" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Process the file content and append to output
    cat "$file" | strip_python_code >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
done

echo "Minimal serialization complete. Output saved to $OUTPUT_FILE" 