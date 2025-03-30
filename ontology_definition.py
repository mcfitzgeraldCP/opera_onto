# ontology_definition.py
# -*- coding: utf-8 -*-
"""
Defines the OWL ontology structure (TBox) based on a specification CSV file.
"""

import csv
import logging
from owlready2 import *
from decimal import Decimal
from datetime import datetime, date, time

logger = logging.getLogger(__name__)

# Mapping from XSD types in the spec to Python types/owlready2 constructs
XSD_TYPE_MAP = {
    "xsd:string": str,
    "xsd:decimal": Decimal,
    "xsd:integer": int,
    "xsd:dateTime": datetime,
    "xsd:date": date,
    "xsd:time": time,
    "xsd:boolean": bool,
    "xsd:anyURI": str,
    "xsd:string (with lang tag)": locstr,
    # Add more mappings if needed
}

def parse_specification(spec_file_path):
    """Parses the ontology specification CSV file."""
    logger.info(f"Parsing specification file: {spec_file_path}")
    spec = []
    try:
        with open(spec_file_path, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                spec.append(row)
        logger.info(f"Successfully parsed {len(spec)} rows from specification.")
        return spec
    except FileNotFoundError:
        logger.error(f"Specification file not found: {spec_file_path}")
        raise
    except Exception as e:
        logger.error(f"Error parsing specification file {spec_file_path}: {e}")
        raise

def define_ontology_structure(onto, specification):
    """Defines OWL classes and properties based on the parsed specification."""
    logger.info(f"Defining ontology structure in: {onto.base_iri}")
    defined_classes = {}
    defined_properties = {}

    # --- Pass 1: Define Classes ---
    logger.debug("--- Defining Classes ---")
    all_classes = set()
    for row in specification:
        class_name = row.get('Proposed OWL Entity')
        if class_name:
            all_classes.add(class_name.strip())

    with onto:
        # Ensure Thing is available if not explicitly listed
        if "Thing" not in all_classes:
             pass # Thing is implicitly available via owlready2

        for class_name in sorted(list(all_classes)): # Sort for deterministic order
            if class_name == "Thing": continue # Skip Thing itself
            if not class_name: continue

            if class_name not in defined_classes:
                try:
                    # Basic class definition, inheritance needs explicit handling if required by spec
                    # Currently assuming flat hierarchy based on spec structure, parent is Thing
                    new_class = types.new_class(class_name, (Thing,))
                    defined_classes[class_name] = new_class
                    logger.debug(f"Defined Class: {new_class.iri}")

                    # Add annotations like comments/labels from spec if desired
                    notes = row.get('Notes/Considerations', '')
                    isa95 = row.get('ISA-95 Concept', '')
                    comments = []
                    if notes: comments.append(f"Notes: {notes}")
                    if isa95: comments.append(f"ISA-95 Concept: {isa95}")
                    if comments:
                       new_class.comment = comments

                except Exception as e:
                    logger.error(f"Error defining class '{class_name}': {e}")

    # --- Pass 2: Define Properties ---
    logger.debug("--- Defining Properties ---")
    properties_to_process = [row for row in specification if row.get('Proposed OWL Property')]

    with onto:
        # Define properties first without inverse, handle inverse in a second pass
        temp_inverse_map = {} # Stores {prop_name: inverse_name}

        for row in properties_to_process:
            prop_name = row.get('Proposed OWL Property').strip()
            if not prop_name or prop_name in defined_properties:
                continue # Skip empty or already defined properties

            prop_type_str = row.get('OWL Property Type', '').strip()
            domain_str = row.get('Domain', '').strip()
            range_str = row.get('Target/Range (xsd:) / Target Class', '').strip()
            characteristics_str = row.get('OWL Property Characteristics', '').strip()
            inverse_prop_name = row.get('Inverse Property', '').strip()

            if not prop_type_str or not domain_str or not range_str:
                 logger.warning(f"Skipping property '{prop_name}' due to missing type, domain, or range in spec.")
                 continue

            # Determine parent classes for the property
            parent_classes = []
            if prop_type_str == 'ObjectProperty':
                parent_classes.append(ObjectProperty)
            elif prop_type_str == 'DatatypeProperty':
                parent_classes.append(DataProperty)
            else:
                logger.warning(f"Unknown property type '{prop_type_str}' for property '{prop_name}'. Skipping.")
                continue

            # Add characteristics
            if 'Functional' in characteristics_str: parent_classes.append(FunctionalProperty)
            if 'InverseFunctional' in characteristics_str: parent_classes.append(InverseFunctionalProperty)
            if 'Transitive' in characteristics_str: parent_classes.append(TransitiveProperty)
            if 'Symmetric' in characteristics_str: parent_classes.append(SymmetricProperty)
            if 'Asymmetric' in characteristics_str: parent_classes.append(AsymmetricProperty)
            if 'Reflexive' in characteristics_str: parent_classes.append(ReflexiveProperty)
            if 'Irreflexive' in characteristics_str: parent_classes.append(IrreflexiveProperty)

            try:
                new_prop = types.new_class(prop_name, tuple(parent_classes))

                # Set Domain
                domain_class = defined_classes.get(domain_str)
                if domain_class:
                    new_prop.domain = [domain_class]
                    logger.debug(f"Set domain for {prop_name} to {domain_class.name}")
                else:
                    logger.warning(f"Domain class '{domain_str}' not found for property '{prop_name}'. Skipping domain assignment.")

                # Set Range
                if prop_type_str == 'ObjectProperty':
                    # Handle potential multiple range classes like "ClassA | ClassB"
                    range_class_names = [rc.strip() for rc in range_str.split('|')]
                    prop_range = []
                    for rc_name in range_class_names:
                        range_class = defined_classes.get(rc_name)
                        if range_class:
                            prop_range.append(range_class)
                        else:
                             logger.warning(f"Range class '{rc_name}' not found for object property '{prop_name}'.")
                    if prop_range:
                        new_prop.range = prop_range
                        logger.debug(f"Set range for {prop_name} to {[rc.name for rc in prop_range]}")
                    else:
                         logger.warning(f"Could not set any valid range for object property '{prop_name}'.")

                elif prop_type_str == 'DatatypeProperty':
                    target_type = XSD_TYPE_MAP.get(range_str)
                    if target_type:
                        new_prop.range = [target_type]
                        logger.debug(f"Set range for {prop_name} to {target_type.__name__ if hasattr(target_type, '__name__') else target_type}")
                    else:
                        logger.warning(f"Unknown XSD type '{range_str}' for property '{prop_name}'. Skipping range assignment.")

                 # Add annotations
                notes = row.get('Notes/Considerations', '')
                isa95 = row.get('ISA-95 Concept', '')
                comments = []
                if notes: comments.append(f"Notes: {notes}")
                if isa95: comments.append(f"ISA-95 Concept: {isa95}")
                if comments:
                    new_prop.comment = comments


                defined_properties[prop_name] = new_prop
                logger.debug(f"Defined Property: {new_prop.iri} of type {prop_type_str}")

                # Store inverse relationship for later processing
                if inverse_prop_name:
                    temp_inverse_map[prop_name] = inverse_prop_name

            except Exception as e:
                logger.error(f"Error defining property '{prop_name}': {e}")

        # --- Pass 3: Set Inverse Properties ---
        logger.debug("--- Setting Inverse Properties ---")
        for prop_name, inverse_name in temp_inverse_map.items():
            prop = defined_properties.get(prop_name)
            inverse_prop = defined_properties.get(inverse_name)

            if prop and inverse_prop:
                try:
                    prop.inverse_property = inverse_prop
                    logger.debug(f"Set inverse_property for {prop.name} to {inverse_prop.name}")
                except Exception as e:
                    logger.error(f"Error setting inverse property for '{prop_name}' and '{inverse_name}': {e}")
            elif not prop:
                 logger.warning(f"Property '{prop_name}' not found while trying to set inverse.")
            elif not inverse_prop:
                 logger.warning(f"Inverse property '{inverse_name}' not found for property '{prop_name}'.")


    # --- Pass 4: Define Property Restrictions (Optional - Basic Domain/Range handled above) ---
    # More complex restrictions (min/max cardinality > 1, exactly, value) can be added here
    # if the specification requires it using owlready2's restriction syntax.
    # The current spec primarily uses Domain/Range and Characteristics.
    logger.debug("--- Skipping complex property restrictions (add if needed based on spec) ---")

    logger.info("Ontology structure definition complete.")
    return defined_classes, defined_properties

# Example usage (if run directly)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    spec_path = 'OPERA_ISA95_OWL_ONT_RICH.csv' # Replace with your actual spec file path
    test_onto = get_ontology("http://example.com/test_ontology_definition.owl")
    try:
        spec_data = parse_specification(spec_path)
        define_ontology_structure(test_onto, spec_data)
        print("\nDefined Classes:")
        for c in test_onto.classes(): print(c)
        print("\nDefined Object Properties:")
        for p in test_onto.object_properties(): print(p)
        print("\nDefined Data Properties:")
        for p in test_onto.data_properties(): print(p)
    except Exception as e:
        logger.exception("Failed to define ontology structure.")