#!/usr/bin/env python3
"""
Script to find unused properties in the ontology specification.
"""
import csv
import os
import sys
import importlib.util

# Add parent directory to path to import from src package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def parse_spec_file(spec_file_path):
    """Parse the CSV specification file to extract property definitions."""
    all_properties = []
    try:
        with open(spec_file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                prop_name = row.get('Proposed OWL Property', '').strip()
                if prop_name and prop_name != 'N/A':
                    all_properties.append(prop_name)
    except Exception as e:
        print(f"Error parsing specification file: {e}")
        sys.exit(1)
    return all_properties

def parse_data_file(data_file_path):
    """Parse the data CSV file to extract available column names."""
    data_columns = []
    try:
        with open(data_file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)  # Get the header row
            data_columns = [col.strip() for col in headers]
    except Exception as e:
        print(f"Error parsing data file: {e}")
        sys.exit(1)
    return data_columns

def analyze_properties(spec_file_path, undefined_properties):
    """Analyze properties to identify unused ones."""
    # Parse the specification file to get defined properties
    defined_properties = parse_spec_file(spec_file_path)
    
    # Convert undefined_properties from string to list
    if isinstance(undefined_properties, str):
        undefined_props_list = [p.strip() for p in undefined_properties.split(',')]
    else:
        undefined_props_list = undefined_properties
    
    # Find properties defined in spec but not being accessed
    potentially_unused = set(defined_properties) - set(undefined_props_list)
    
    print(f"Total properties defined in specification: {len(defined_properties)}")
    print(f"Properties being requested by code: {len(undefined_props_list)}")
    print(f"Properties defined but not accessed: {len(potentially_unused)}")
    print("\nPotentially unused properties:")
    for prop in sorted(potentially_unused):
        print(f"- {prop}")
    
    return potentially_unused

def main():
    # Check command line arguments
    if len(sys.argv) < 3:
        print("Usage: python finds_unused_properties.py <spec_file_path> <list_of_undefined_properties>")
        print("Example: python finds_unused_properties.py ../Ontology_specifications/OPERA_ISA95_OWL_ONT_V25.csv \"prop1, prop2, prop3\"")
        sys.exit(1)
    
    spec_file_path = sys.argv[1]
    undefined_properties = sys.argv[2]
    
    # Validate paths
    if not os.path.exists(spec_file_path):
        print(f"Error: Specification file not found at: {spec_file_path}")
        sys.exit(1)
    
    # Analyze properties
    unused_properties = analyze_properties(spec_file_path, undefined_properties)

if __name__ == "__main__":
    main() 