# Import the owlready2 library
from owlready2 import *

# Specify the path to your ontology OWL file
# Replace "your_ontology_file.owl" with the actual path or URL
ontology_path = "mx_tp_feb25_ontology.owl"

onto = get_ontology(ontology_path).load()
print(f"Ontology loaded successfully from: {ontology_path}")
actual_base_iri = onto.base_iri # Or paste the string directly "http://..."
print(f"Base IRI: {onto.base_iri}")


# Load the ontology
# get_ontology() creates an Ontology object representing your file
# .load() parses the file and loads it into memory
try:
    classes_list = list(onto.classes())
    print(f"\nFound {len(classes_list)} classes.")

    # 2. Print the first few classes (optional, good for a quick look)
    if classes_list:
        print("First few classes:")
        for cls in classes_list[:10]: # Print up to the first 10 classes
             print(f"- {cls.name} (IRI: {cls.iri})")

    # 3. Check for specific key classes from your specification
    # Replace 'ProductionLine' and 'EventRecord' if your actual class names differ
    expected_classes = ["ProductionLine", "EventRecord", "Equipment", "OperationalReason"]
    print("\nChecking for key classes:")
    for class_name in expected_classes:
        found_class = onto.search_one(iri=f"{onto.base_iri}{class_name}") # Assumes classes are in the base namespace
        if found_class:
            print(f"- Found class: {found_class.name}")
        else:
            # Try searching by label if direct IRI search fails (less precise)
            found_class_by_label = onto.search_one(label=class_name)
            if found_class_by_label:
                 print(f"- Found class by label (check IRI): {found_class_by_label.name} (IRI: {found_class_by_label.iri})")
            else:
                 print(f"- *** Class '{class_name}' not found directly. Check ontology details (namespace, exact name).")

except Exception as e:
    print(f"Error loading ontology: {e}")
    print("Please ensure the file path is correct and the file is a valid OWL ontology.")

# You can now access classes and properties via the 'onto' object, e.g., onto.ProductionLine
# The default_world object (used for SPARQL) is automatically populated when you load the ontology.

import time
from datetime import datetime

print("\nStarting query execution...")
start_time = time.time()

# First, let's check how many instances we're dealing with
print("\nChecking instance counts:")
try:
    line_count = len(list(default_world.sparql(f"""
        PREFIX : <{actual_base_iri}>
        SELECT DISTINCT ?line WHERE {{ ?line a :ProductionLine }}
    """)))
    event_count = len(list(default_world.sparql(f"""
        PREFIX : <{actual_base_iri}>
        SELECT DISTINCT ?event WHERE {{ ?event a :EventRecord }}
    """)))
    equip_count = len(list(default_world.sparql(f"""
        PREFIX : <{actual_base_iri}>
        SELECT DISTINCT ?equip WHERE {{ ?equip a :Equipment }}
    """)))
    
    # Test query for equipment events
    equip_event_count = len(list(default_world.sparql(f"""
        PREFIX : <{actual_base_iri}>
        SELECT DISTINCT ?event WHERE {{
            ?event a :EventRecord .
            ?event :involvesResource ?equip .
            ?equip a :Equipment .
        }}
    """)))
    
    # Debug query for event relationships
    print("\nChecking event relationships:")
    event_relationships = list(default_world.sparql(f"""
        PREFIX : <{actual_base_iri}>
        SELECT DISTINCT (COUNT(?equipEvent) AS ?count) WHERE {{
            ?equipEvent a :EventRecord .
            ?equipEvent :involvesResource ?equip .
            ?equip a :Equipment .
            ?equipEvent :isPartOfLineEvent ?lineEvent .
        }}
    """))
    print(f"Number of equipment events with line event relationships: {event_relationships[0][0]}")
    
    # Debug query for equipment events with durations
    print("\nChecking equipment event durations:")
    equip_durations = list(default_world.sparql(f"""
        PREFIX : <{actual_base_iri}>
        SELECT DISTINCT (COUNT(?event) AS ?count) (SUM(?duration) AS ?totalDuration) WHERE {{
            ?event a :EventRecord .
            ?event :involvesResource ?equip .
            ?equip a :Equipment .
            ?event :reportedDurationMinutes ?duration .
        }}
    """))
    print(f"Number of equipment events with durations: {equip_durations[0][0]}")
    print(f"Total equipment event duration: {equip_durations[0][1]}")
    
    # Debug query for equipment events with line events and durations
    print("\nChecking equipment events with line events and durations:")
    equip_line_durations = list(default_world.sparql(f"""
        PREFIX : <{actual_base_iri}>
        SELECT DISTINCT (COUNT(?equipEvent) AS ?count) (SUM(?duration) AS ?totalDuration) WHERE {{
            ?equipEvent a :EventRecord .
            ?equipEvent :involvesResource ?equip .
            ?equip a :Equipment .
            ?equipEvent :isPartOfLineEvent ?lineEvent .
            ?equipEvent :reportedDurationMinutes ?duration .
        }}
    """))
    print(f"Number of equipment events with line events and durations: {equip_line_durations[0][0]}")
    print(f"Total duration for equipment events with line events: {equip_line_durations[0][1]}")
    
    # Debug query for equipment-line relationships
    equip_line_relationships = list(default_world.sparql(f"""
        PREFIX : <{actual_base_iri}>
        SELECT DISTINCT (COUNT(?equip) AS ?count) WHERE {{
            ?equip a :Equipment .
            ?equip :isPartOfProductionLine ?line .
        }}
    """))
    print(f"Number of equipment-line relationships: {equip_line_relationships[0][0]}")
    
    print(f"\nNumber of ProductionLines: {line_count}")
    print(f"Number of EventRecords: {event_count}")
    print(f"Number of Equipment: {equip_count}")
    print(f"Number of Equipment Events: {equip_event_count}")
except Exception as e:
    print(f"Error counting instances: {e}")

print("\nExecuting main query...")
query_start = time.time()

queryString = f"""
PREFIX : <{actual_base_iri}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT
    ?lineId
    (SUM(?lineDuration) AS ?totalLineReportedMinutes)
    (SUM(?equipDuration) AS ?totalEquipmentReportedMinutes)
WHERE {{
    ?line a :ProductionLine .
    ?line :lineId ?lineId .
    {{
        # Line events
        ?event a :EventRecord .
        ?event :reportedDurationMinutes ?duration .
        ?event :involvesResource ?line .
        BIND(?duration AS ?lineDuration)
        BIND(0 AS ?equipDuration)
    }} UNION {{
        # Equipment events that are part of line events
        ?lineEvent a :EventRecord .
        ?lineEvent :involvesResource ?line .
        ?equipEvent a :EventRecord .
        ?equipEvent :involvesResource ?equip .
        ?equip a :Equipment .
        ?equipEvent :isPartOfLineEvent ?lineEvent .
        ?equipEvent :reportedDurationMinutes ?duration .
        BIND(0 AS ?lineDuration)
        BIND(?duration AS ?equipDuration)
    }}
}}
GROUP BY ?lineId
ORDER BY ?lineId
"""

# Execute the query with timeout
results = []
try:
    query_results = default_world.sparql(queryString)
    results = list(query_results)  # Convert to list to force execution
    query_time = time.time() - query_start
    print(f"Query execution completed in {query_time:.2f} seconds")
    print(f"Number of results: {len(results)}")
except Exception as e:
    print(f"Error executing query: {e}")
    print(f"Query was running for {time.time() - query_start:.2f} seconds before error")
    print("No results to process due to query error.")
    exit(1)

# Process and print results
print("\nProcessing results...")
process_start = time.time()
print("Line ID | Total Line Reported Minutes | Total Equipment Reported Minutes")
print("---------------------------------------------------------------------")
for row in results:
    try:
        line_id = str(row[0])
        # Handle the values directly, ensuring we have valid numbers
        line_minutes = float(row[1]) if row[1] is not None else 0.0
        equip_minutes = float(row[2]) if row[2] is not None else 0.0
        print(f"{line_id:<7} | {line_minutes:<27.2f} | {equip_minutes:.2f}")
    except (ValueError, TypeError) as e:
        print(f"Error processing row: {row}")
        print(f"Error details: {e}")
        continue

process_time = time.time() - process_start
total_time = time.time() - start_time
print(f"\nProcessing completed in {process_time:.2f} seconds")
print(f"Total execution time: {total_time:.2f} seconds")

print("\nNote: 'Reported Minutes' currently sums ':reportedDurationMinutes' for ALL associated events.")
print("Refine by adding FILTER on :eventHasState or :eventHasReason for specific downtime.")