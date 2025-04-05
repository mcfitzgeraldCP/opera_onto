import owlready2
import pandas as pd
import matplotlib.pyplot as plt
import io # Required for SPARQLWrapper result parsing if needed, good practice

# Load the ontology
onto = owlready2.default_world.get_ontology("mx_tp_feb25_ontology.owl").load()
base_iri = onto.base_iri

# Debugging - Print classes and properties in the ontology
print("=== Ontology debugging information ===")
print(f"Base IRI: {base_iri}")
print("Available classes:")
for cls in onto.classes():
    print(f" - {cls.name}")

print("\nChecking for key classes used in query:")
event_record_exists = "EventRecord" in [cls.name for cls in onto.classes()]
production_line_exists = "ProductionLine" in [cls.name for cls in onto.classes()]
print(f" - EventRecord exists: {event_record_exists}")
print(f" - ProductionLine exists: {production_line_exists}")

print("\nChecking for individuals:")
event_records = list(onto.search(type=onto.EventRecord if event_record_exists else None))
print(f" - Number of EventRecord instances: {len(event_records)}")
if event_records and event_record_exists:
    sample_event = event_records[0]
    print(f" - Sample EventRecord: {sample_event}")
    
    # Print all properties available on the first EventRecord
    print(" - Available properties on the first EventRecord:")
    for prop in dir(sample_event):
        if not prop.startswith('_') and prop not in ['comment', 'label', 'is_a', 'INDIRECT_is_a', 'namespace', 'storid']:
            value = getattr(sample_event, prop)
            if not callable(value):
                print(f"   * {prop}: {value}")

# Check production lines
production_lines = list(onto.search(type=onto.ProductionLine if production_line_exists else None))
print(f" - Number of ProductionLine instances: {len(production_lines)}")
if production_lines and production_line_exists:
    sample_line = production_lines[0]
    print(f" - Sample ProductionLine: {sample_line}")
    
    # Print properties of the first ProductionLine
    print(" - Available properties on the first ProductionLine:")
    for prop in dir(sample_line):
        if not prop.startswith('_') and prop not in ['comment', 'label', 'is_a', 'INDIRECT_is_a', 'namespace', 'storid']:
            value = getattr(sample_line, prop)
            if not callable(value):
                print(f"   * {prop}: {value}")
print("=====================================")

# Add a simple check for a specific property on the first event record
print("=== Property Check ===")
event_records = list(onto.search(type=onto.EventRecord))
if event_records:
    sample_event = event_records[0]
    print(f"Sample EventRecord: {sample_event}")
    # Check specific properties from the CSV file
    property_names = [
        "downtimeMinutes", 
        "involvesResource", 
        "eventHasReason"
    ]
    for prop_name in property_names:
        # Check if property exists in owlready2
        if hasattr(onto, prop_name):
            print(f"Ontology has property definition for: {prop_name}")
            # Try to get the property value for this event
            try:
                value = getattr(sample_event, prop_name, "Property not found on instance")
                print(f" - Value on sample event: {value}")
            except Exception as e:
                print(f" - Error accessing property on instance: {e}")
        else:
            print(f"Ontology MISSING property definition for: {prop_name}")
print("=====================")

# Define the prefix for the ontology namespace
prefixes = f"""PREFIX onto: <{base_iri}>
               PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
               PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
               PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            """

# First run a simple test query to check what properties exist on EventRecord instances
query1 = prefixes + """
    SELECT DISTINCT ?property ?value
    WHERE {
        ?eventRecord a onto:EventRecord .
        ?eventRecord ?property ?value .
    }
    LIMIT 20
"""

# Main query to find downtime by line and reason - using correct property names from CSV
query2 = prefixes + """
    SELECT ?lineId ?reasonDesc (SUM(?durationMins) AS ?totalDowntime)
    WHERE {
        # Find Event Records with duration
        ?eventRecord a onto:EventRecord .
        ?eventRecord onto:reportedDurationMinutes ?durationMins .
        FILTER(?durationMins > 0) # Ensure it's actual tracked time

        # Link event to the Production Line involved
        ?eventRecord onto:involvesResource ?resource .
        ?resource a onto:ProductionLine .
        ?resource onto:lineId ?lineId .

        # Link event to its reason
        ?eventRecord onto:eventHasReason ?reason .
        ?reason onto:reasonDescription ?reasonDesc .
    }
    GROUP BY ?lineId ?reasonDesc
    ORDER BY ?lineId DESC(?totalDowntime)
    LIMIT 20
"""

try:
    print("=== Running property discovery query ===")
    results = list(owlready2.default_world.sparql(query1))
    if not results:
        print("Property discovery query returned no results. This suggests a major issue with the ontology structure.")
    else:
        # Display property results
        df = pd.DataFrame(results, columns=["Property", "Value"])
        print("--- Available Properties in EventRecord Instances ---")
        print(df.to_string(index=False))
    
    print("\n=== Running downtime analysis query ===")
    results = list(owlready2.default_world.sparql(query2))
    if not results:
        print("Downtime analysis query returned no results. This may indicate missing property instances.")
        
        # Try a simpler query to check each component
        print("\n=== Checking reportedDurationMinutes property values ===")
        check_query = prefixes + """
            SELECT ?event ?durationMins 
            WHERE { ?event a onto:EventRecord . ?event onto:reportedDurationMinutes ?durationMins . } 
            LIMIT 5
        """
        check_results = list(owlready2.default_world.sparql(check_query))
        if check_results:
            print(f"Found {len(check_results)} events with reportedDurationMinutes property")
            for r in check_results:
                print(f" - Event: {r[0]}, Duration: {r[1]}")
        else:
            print("No events with reportedDurationMinutes property found")
            
        print("\n=== Checking Production Lines ===")
        check_query = prefixes + """
            SELECT ?line ?lineId WHERE { ?line a onto:ProductionLine . ?line onto:lineId ?lineId . } LIMIT 5
        """
        check_results = list(owlready2.default_world.sparql(check_query))
        if check_results:
            print(f"Found {len(check_results)} production lines with lineId property")
            for r in check_results:
                print(f" - Line: {r[0]}, ID: {r[1]}")
        else:
            print("No production lines with lineId property found")
            
        print("\n=== Checking Reasons ===")
        check_query = prefixes + """
            SELECT ?reason ?desc WHERE { ?reason a onto:OperationalReason . ?reason onto:reasonDescription ?desc . } LIMIT 5
        """
        check_results = list(owlready2.default_world.sparql(check_query))
        if check_results:
            print(f"Found {len(check_results)} reasons with reasonDescription property")
            for r in check_results:
                print(f" - Reason: {r[0]}, Description: {r[1]}")
        else:
            print("No reasons with reasonDescription property found")
    else:
        # Process the main query results
        df = pd.DataFrame(results, columns=["LineID", "Reason", "TotalDowntimeMinutes"])
        # Convert duration from Literal to numeric
        df['TotalDowntimeMinutes'] = pd.to_numeric(df['TotalDowntimeMinutes'])

        print("--- Downtime Analysis Results ---")
        print(df.to_string(index=False))

except Exception as e:
    print(f"An error occurred executing SPARQL query or processing results: {e}")
    # Print the generated SQL for debugging if using native engine
    try:
        prepared_query = owlready2.default_world.prepare_sparql(query1)
        print("Generated SQL:", prepared_query.sql)
    except Exception as e2:
        print(f"Could not get SQL: {e2}")