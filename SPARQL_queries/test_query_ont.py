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
