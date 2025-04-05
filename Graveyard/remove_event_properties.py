#!/usr/bin/env python
"""
Script to remove event-to-event linking properties from the OPERA ontology specification CSV.
TKT-BUG-001: Remove isPartOfLineEvent and hasDetailedEquipmentEvent properties.
"""
import csv
import sys
import os

def remove_event_properties(input_file, output_file):
    """
    Process the input CSV file and remove rows containing 
    isPartOfLineEvent and hasDetailedEquipmentEvent properties.
    """
    # Properties to remove
    properties_to_remove = ['isPartOfLineEvent', 'hasDetailedEquipmentEvent']
    
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        rows = list(reader)
        
    # Filter rows, excluding those with the specified properties
    filtered_rows = []
    removed_count = 0
    
    for row in rows:
        if len(row) > 3 and row[3] in properties_to_remove:
            removed_count += 1
            print(f"Removing row with property: {row[3]}")
            continue
        filtered_rows.append(row)
    
    # Write the filtered data to the output file
    with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(filtered_rows)
    
    print(f"Processing complete. Removed {removed_count} rows. Wrote {len(filtered_rows)} rows to {output_file}")

if __name__ == "__main__":
    # Check if input and output file paths are provided as command-line arguments
    if len(sys.argv) < 3:
        print("Usage: python remove_event_properties.py <input_file> <output_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
    
    remove_event_properties(input_file, output_file) 