#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e
# Treat unset variables as an error when substituting.
# set -u # Optional: uncomment for stricter variable checking
# Pipe commands return the exit status of the last command to exit non-zero.
set -o pipefail

# Default values
keep_comments_flag=false
output_file=""
input_path=""

# --- Usage instructions ---
usage() {
  echo "Usage: $0 -i <input_path> [-o <output_file>] [-k]"
  echo ""
  echo "Flattens and optionally strips comments/docstrings from Python source code."
  echo ""
  echo "Arguments:"
  echo "  -i <input_path>   Required. Path to the source Python file or directory."
  echo "  -o <output_file>  Optional. Path to the output file. Defaults to '<input_basename>_flat.txt'."
  echo "  -k                Optional. Keep comments and docstrings (default is to strip)."
  echo "  -h                Display this help message."
  echo ""
  echo "Example (strip comments/docstrings from a directory):"
  echo "  $0 -i my_python_project -o flattened_code.py"
  echo ""
  echo "Example (keep comments/docstrings from a single file):"
  echo "  $0 -i my_script.py -k -o original_flat.py"
  exit 1
}

# --- Argument Parsing ---
while getopts ":i:o:kh" opt; do
  case ${opt} in
    i )
      input_path=$OPTARG
      ;;
    o )
      output_file=$OPTARG
      ;;
    k )
      keep_comments_flag=true
      ;;
    h )
      usage
      ;;
    \? )
      echo "Invalid option: $OPTARG" 1>&2
      usage
      ;;
    : )
      echo "Invalid option: $OPTARG requires an argument" 1>&2
      usage
      ;;
  esac
done
shift $((OPTIND -1))

# --- Input Validation ---
if [[ -z "$input_path" ]]; then
  echo "Error: Input path (-i) is required." 1>&2
  usage
fi

if [[ ! -e "$input_path" ]]; then
  echo "Error: Input path '$input_path' does not exist." 1>&2
  exit 1
fi

# --- Set default output file if not specified ---
if [[ -z "$output_file" ]]; then
  input_basename=$(basename "$input_path")
  input_name="${input_basename%.*}"
  parent_dir=$(basename "$(dirname "$(realpath "$input_path")")")
  output_file="${parent_dir}_${input_basename}_flat.txt"
  echo "No output file specified. Using default: $output_file"
fi

# --- Python script to flatten and optionally strip comments ---
python_script=$(cat <<'EOF'
import os
import sys
import ast
import re

def is_python_file(filename):
    return filename.endswith('.py') and not filename.startswith('__')

def strip_docstrings(node):
    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
        # More robust docstring removal from the example
        if node.body and isinstance(node.body[0], ast.Expr) and hasattr(node.body[0].value, 'value') and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:]
        elif node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Str):
            # For older Python versions
            node.body = node.body[1:]
    
    for child in ast.iter_child_nodes(node):
        strip_docstrings(child)
    return node

def process_file(file_path, keep_comments=False):
    print(f"Processing file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            source = file.read()
        
        if keep_comments:
            return source
        else:
            # Parse the source code into an AST
            tree = ast.parse(source)
            
            # Strip docstrings using the more robust method
            tree = strip_docstrings(tree)
            
            # Convert back to source code
            try:
                # For Python 3.9+
                result = ast.unparse(tree)
            except AttributeError:
                # For older Python versions, fall back to astunparse
                import astunparse
                result = astunparse.unparse(tree)
                
            return result
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return f"# ERROR processing {file_path}: {str(e)}\n"

def process_directory(directory_path, keep_comments=False):
    combined_code = ""
    processed_files = 0
    
    print(f"Searching for Python files in: {directory_path}")
    
    # Get the base directory name for the headers
    base_dir = os.path.basename(directory_path)
    
    for root, _, files in os.walk(directory_path):
        python_files = [f for f in files if is_python_file(f)]
        if python_files:
            print(f"Found {len(python_files)} Python files in {root}")
        
        for file in sorted(python_files):
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, os.path.dirname(directory_path))
            
            # Add a header comment to indicate the source file
            file_header = f"\n===========================================\nFILE: {relative_path}\n===========================================\n\n"
            combined_code += file_header
            
            # Process the file
            file_code = process_file(file_path, keep_comments)
            combined_code += file_code + "\n\n"
            processed_files += 1
    
    print(f"Total files processed: {processed_files}")
    return combined_code

def main():
    input_path = sys.argv[1]
    output_file = sys.argv[2]
    keep_comments = sys.argv[3].lower() == 'true'
    
    print(f"Processing: {input_path}")
    print(f"Output will be saved to: {output_file}")
    print(f"Keep comments: {keep_comments}")
    
    if os.path.isdir(input_path):
        result = process_directory(input_path, keep_comments)
    elif os.path.isfile(input_path):
        file_header = f"\n===========================================\nFILE: {os.path.basename(input_path)}\n===========================================\n\n"
        result = file_header + process_file(input_path, keep_comments)
    else:
        sys.exit(f"Error: {input_path} is not a valid file or directory")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"Successfully created flattened file: {output_file}")

if __name__ == "__main__":
    main()
EOF
)

# --- Install required Python packages if needed ---
echo "Checking for required Python packages..."
# Only try to install astunparse if Python is older than 3.9
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" || {
  if ! pip show astunparse >/dev/null 2>&1; then
    echo "Installing required Python package: astunparse"
    pip install astunparse
  fi
}

# --- Execute the Python script ---
echo "Flattening Python code from '$input_path' to '$output_file'..."
echo "Keep comments: $keep_comments_flag"

# Run the Python flattener script with more detailed output
python -c "$python_script" "$input_path" "$output_file" "$keep_comments_flag"

echo "Flattening complete! Output saved to: $output_file"