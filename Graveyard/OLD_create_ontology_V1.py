# -*- coding: utf-8 -*-
# Combined and Updated Ontology Generation Code

import csv
import logging
import sys
import time as timing
import argparse
import re
from owlready2 import *
from decimal import Decimal, InvalidOperation
from datetime import datetime, date, time # time might not be needed if not used in spec

# --- Configuration ---
DEFAULT_ONTOLOGY_IRI = "http://example.com/manufacturing_ontology.owl"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
SPEC_PARENT_CLASS_COLUMN = 'Parent Class' # Assumed column name for hierarchy

# --- Language Mapping for Alternative Reason Descriptions ---
# Mapping from country descriptions to BCP 47 language tags
COUNTRY_TO_LANGUAGE = {
    "Mexico": "es",
    "United States": "en",
    "Brazil": "pt",
    "France": "fr",
    "Germany": "de",
    "Italy": "it",
    "Spain": "es",
    "Japan": "ja",
    "China": "zh",
    # Add more mappings as needed based on your data
}
DEFAULT_LANGUAGE = "en"  # Default language if country not found in mapping

# --- Default Equipment Class Sequencing ---
DEFAULT_EQUIPMENT_SEQUENCE = {
    "Filler": 1,
    "Cartoner": 2,
    "Bundler": 3,
    "CaseFormer": 4,
    "CasePacker": 5,
    "CaseSealer": 6,
    "Palletizer": 7,
    # Add any other classes with default positions if needed
}

# --- Logging Setup ---
# Basic config will be set in create_ontology.py's main block
# Get root logger for module-level logging configuration
logger = logging.getLogger(__name__) # Logger for definition module
pop_logger = logging.getLogger("ontology_population") # Logger for population module
main_logger = logging.getLogger("create_ontology") # Logger for main script

#======================================================================#
#                   ontology_definition.py Module Code                 #
#======================================================================#

# Mapping from XSD types in the spec to Python types/owlready2 constructs
XSD_TYPE_MAP = {
    "xsd:string": str,
    "xsd:decimal": float,  # Changed from Decimal to float for compatibility with owlready2
    "xsd:integer": int,
    "xsd:dateTime": datetime,
    "xsd:date": date,
    "xsd:time": time,
    "xsd:boolean": bool,
    "xsd:anyURI": str,
    "xsd:string (with lang tag)": locstr,
    # Add more mappings if needed based on your spec
}

def parse_specification(spec_file_path):
    """Parses the ontology specification CSV file."""
    logger.info(f"Parsing specification file: {spec_file_path}")
    spec_list = []
    try:
        with open(spec_file_path, mode='r', encoding='utf-8-sig') as infile: # Use utf-8-sig to handle potential BOM
            reader = csv.DictReader(infile)
            # Basic check for expected columns (optional but recommended)
            # expected_cols = {'Proposed OWL Entity', 'Proposed OWL Property', 'Parent Class', ...}
            # if not expected_cols.issubset(reader.fieldnames):
            #     logger.warning(f"Specification file might be missing expected columns. Found: {reader.fieldnames}")
            for row in reader:
                spec_list.append(row)
        logger.info(f"Successfully parsed {len(spec_list)} rows from specification.")
        return spec_list
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
    class_metadata = {} # Store metadata like notes per class

    # --- Pre-process Spec for Class Metadata and Hierarchy ---
    logger.debug("--- Pre-processing specification for class details ---")
    all_class_names = set()
    class_parents = {} # {child_name: parent_name}
    for i, row in enumerate(specification):
        class_name = row.get('Proposed OWL Entity', '').strip()
        if class_name:
            all_class_names.add(class_name)
            # Store metadata (using first encountered row for simplicity, could collect all)
            if class_name not in class_metadata:
                 class_metadata[class_name] = {
                     'notes': row.get('Notes/Considerations', ''),
                     'isa95': row.get('ISA-95 Concept', ''),
                     'row_index': i # For reference if needed
                 }
            # Store parent class info if column exists
            parent_name = row.get(SPEC_PARENT_CLASS_COLUMN, '').strip()
            if parent_name and parent_name != class_name: # Avoid self-parenting
                 class_parents[class_name] = parent_name
                 all_class_names.add(parent_name) # Ensure parent is also considered a class


    # --- Pass 1: Define Classes with Hierarchy ---
    logger.debug("--- Defining Classes ---")
    with onto:
        # Ensure Thing is available if not explicitly listed
        if "Thing" not in all_class_names:
            pass # Thing is implicitly available via owlready2

        defined_order = [] # Track definition order for hierarchy
        definition_attempts = 0
        max_attempts = len(all_class_names) + 5 # Allow some leeway for complex hierarchies

        classes_to_define = set(all_class_names) - {"Thing"} # Exclude Thing

        while classes_to_define and definition_attempts < max_attempts:
            defined_in_pass = set()
            for class_name in sorted(list(classes_to_define)): # Sort for somewhat deterministic order
                parent_name = class_parents.get(class_name)
                parent_class_obj = Thing # Default parent is Thing

                if parent_name:
                    if parent_name == "Thing":
                        parent_class_obj = Thing
                    elif parent_name in defined_classes:
                        parent_class_obj = defined_classes[parent_name]
                    else:
                        # Parent not defined yet, skip this class for now
                        logger.debug(f"Deferring class '{class_name}', parent '{parent_name}' not defined yet.")
                        continue

                # Define the class
                try:
                    if class_name not in defined_classes:
                        logger.debug(f"Attempting to define Class: {class_name} with Parent: {parent_class_obj.name}")
                        new_class = types.new_class(class_name, (parent_class_obj,))
                        defined_classes[class_name] = new_class
                        defined_order.append(class_name)
                        defined_in_pass.add(class_name)
                        logger.debug(f"Defined Class: {new_class.iri} (Parent: {parent_class_obj.iri})")

                        # Add annotations like comments/labels from pre-processed metadata
                        meta = class_metadata.get(class_name)
                        if meta:
                            comments = []
                            if meta['notes']: comments.append(f"Notes: {meta['notes']}")
                            if meta['isa95']: comments.append(f"ISA-95 Concept: {meta['isa95']}")
                            if comments:
                                new_class.comment = comments
                                logger.debug(f"Added comments to class {class_name}")
                        else:
                             logger.warning(f"No metadata found for class '{class_name}' during annotation.")

                except Exception as e:
                    logger.error(f"Error defining class '{class_name}' with parent '{getattr(parent_class_obj,'name','N/A')}': {e}")
                    # Optionally remove from classes_to_define to prevent infinite loops if error is persistent
                    defined_in_pass.add(class_name) # Remove from consideration in this loop iteration

            classes_to_define -= defined_in_pass
            definition_attempts += 1
            if not defined_in_pass and classes_to_define:
                logger.error(f"Could not define remaining classes (possible circular dependency or missing parents): {classes_to_define}")
                break # Avoid infinite loop

        if classes_to_define:
             logger.warning(f"Failed to define the following classes: {classes_to_define}")

    # --- Pass 2: Define Properties ---
    logger.debug("--- Defining Properties ---")
    properties_to_process = [row for row in specification if row.get('Proposed OWL Property')]

    with onto:
        # Define properties first without inverse, handle inverse in a second pass
        temp_inverse_map = {} # Stores {prop_name: inverse_name}

        for row in properties_to_process:
            prop_name = row.get('Proposed OWL Property','').strip()
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
            base_prop_type = None
            if prop_type_str == 'ObjectProperty':
                base_prop_type = ObjectProperty
            elif prop_type_str == 'DatatypeProperty':
                base_prop_type = DataProperty
            else:
                logger.warning(f"Unknown property type '{prop_type_str}' for property '{prop_name}'. Skipping.")
                continue

            parent_classes.append(base_prop_type)

            # Add characteristics
            # Note: owlready2 might implicitly handle some characteristic implications (e.g., Symmetric -> Reflexive is debated)
            # We define based on explicit spec entries.
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
                domain_class_names = [dc.strip() for dc in domain_str.split('|')]
                prop_domain = []
                valid_domain_found = False
                for dc_name in domain_class_names:
                    domain_class = defined_classes.get(dc_name)
                    if domain_class:
                        prop_domain.append(domain_class)
                        valid_domain_found = True
                    elif dc_name == "Thing": # Allow Thing as domain
                         prop_domain.append(Thing)
                         valid_domain_found = True
                    else:
                        logger.warning(f"Domain class '{dc_name}' not found for property '{prop_name}'.")

                if prop_domain:
                    new_prop.domain = prop_domain # Assign list directly for union domain
                    logger.debug(f"Set domain for {prop_name} to {[dc.name for dc in prop_domain]}")
                elif not valid_domain_found:
                    logger.warning(f"No valid domain classes found for property '{prop_name}'. Skipping domain assignment.")

                # Set Range
                if base_prop_type is ObjectProperty:
                    range_class_names = [rc.strip() for rc in range_str.split('|')]
                    prop_range = []
                    valid_range_found = False
                    for rc_name in range_class_names:
                        range_class = defined_classes.get(rc_name)
                        if range_class:
                            prop_range.append(range_class)
                            valid_range_found = True
                        elif rc_name == "Thing": # Allow Thing as range
                             prop_range.append(Thing)
                             valid_range_found = True
                        else:
                            logger.warning(f"Range class '{rc_name}' not found for object property '{prop_name}'.")
                    if prop_range:
                        new_prop.range = prop_range # Assign list directly for union range
                        logger.debug(f"Set range for {prop_name} to {[rc.name for rc in prop_range]}")
                    elif not valid_range_found:
                        logger.warning(f"Could not set any valid range for object property '{prop_name}'.")

                elif base_prop_type is DataProperty:
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
                if inverse_prop_name and base_prop_type is ObjectProperty:
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
                    # Check if already set (e.g., if spec defines inverse on both sides)
                    if not prop.inverse_property:
                        prop.inverse_property = inverse_prop
                        logger.debug(f"Set inverse_property for {prop.name} to {inverse_prop.name}")
                    elif prop.inverse_property == inverse_prop:
                         logger.debug(f"Inverse property for {prop.name} already correctly set to {inverse_prop.name}.")
                    else:
                         logger.warning(f"Inverse property for {prop.name} is already set to {prop.inverse_property.name}, but spec also suggests {inverse_prop.name}. Keeping the first assignment.")

                except Exception as e:
                    logger.error(f"Error setting inverse property for '{prop_name}' and '{inverse_name}': {e}")
            elif not prop:
                logger.warning(f"Property '{prop_name}' not found while trying to set inverse '{inverse_name}'.")
            elif not inverse_prop:
                logger.warning(f"Inverse property '{inverse_name}' not found for property '{prop_name}'.")


    # --- Pass 4: Define Property Restrictions (Optional) ---
    # More complex restrictions (min/max cardinality, exactly, value) can be added here
    # by iterating through the specification again and finding rows that define restrictions
    # on specific classes using owlready2's restriction syntax (e.g., Class.some(Property, Value)).
    logger.debug("--- Skipping complex property restrictions (add implementation if needed based on spec) ---")

    logger.info("Ontology structure definition complete.")
    return defined_classes, defined_properties

#======================================================================#
#                 ontology_population.py Module Code                   #
#======================================================================#

# --- Helper Functions ---

def parse_equipment_class(equipment_name):
    """
    Parses the EquipmentClass from the EQUIPMENT_NAME.
    Rule: Extracts the part after the last underscore.
    Example: FIPCO009_Filler -> Filler
    """
    if not equipment_name or not isinstance(equipment_name, str):
        return None
    if '_' in equipment_name:
        return equipment_name.split('_')[-1]
    pop_logger.debug(f"No underscore found in EQUIPMENT_NAME '{equipment_name}', using whole name as class.")
    return equipment_name # Fallback if no underscore

def safe_cast(value, target_type, default=None):
    """Safely casts a value to a target type, returning default on failure."""
    if value is None or value == '':
        return default
    try:
        original_value_repr = repr(value) # For logging
        value_str = str(value).strip()

        if target_type is str:
            return value_str
        if target_type is int:
            # Handle potential floats in data like '224.0'
            return int(float(value_str))
        if target_type is float:
            return float(value_str)
        if target_type is Decimal:
             # Convert to float instead of Decimal for compatibility with owlready2
             cleaned_value = value_str.replace(',', '')
             return float(cleaned_value)
        if target_type is bool:
            val_lower = value_str.lower()
            if val_lower in ['true', '1', 't', 'y', 'yes']:
                return True
            elif val_lower in ['false', '0', 'f', 'n', 'no']:
                return False
            else:
                pop_logger.warning(f"Could not interpret {original_value_repr} as boolean.")
                return default
        if target_type is datetime:
            # Try parsing common formats, including the one in the sample data
            # '2025-02-05 22:40:21.000 -0500'
            # owlready2 stores datetime naive, stripping timezone info after parsing
            fmts = [
                "%Y-%m-%d %H:%M:%S.%f %z", # Format with timezone and microseconds
                "%Y-%m-%d %H:%M:%S %z",    # Format with timezone, no microseconds
                "%Y-%m-%d %H:%M:%S.%f",    # Format without timezone, with microseconds
                "%Y-%m-%d %H:%M:%S",       # Format without timezone, no microseconds
                "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO 8601 format often seen
                "%Y-%m-%dT%H:%M:%S%z",     # ISO 8601 format
                "%Y-%m-%dT%H:%M:%S.%f",    # ISO 8601 format naive
                "%Y-%m-%dT%H:%M:%S",       # ISO 8601 format naive
                "%Y-%m-%d",                # Date only
            ]
            parsed_dt = None
            # Clean common variations like trailing Z or space before timezone
            clean_value = value_str.replace('Z', '+0000')
             # Handle space separated timezone offset like "+05 00" -> "+0500"
            clean_value = re.sub(r'([+-])(\d{2})\s(\d{2})$', r'\1\2\3', clean_value)

            for fmt in fmts:
                try:
                    parsed_dt = datetime.strptime(clean_value, fmt)
                    # Make timezone-aware if timezone info was present, then convert to UTC?
                    # owlready2 seems to prefer naive datetimes representing UTC or local implicitly.
                    # For consistency, let's store naive. If parsed with TZ, log it.
                    if parsed_dt.tzinfo:
                        pop_logger.debug(f"Parsed datetime {original_value_repr} with timezone {parsed_dt.tzinfo}, storing as naive.")
                        # Example: Convert to UTC then make naive
                        # from datetime import timezone
                        # parsed_dt = parsed_dt.astimezone(timezone.utc).replace(tzinfo=None)
                        # Or just make naive directly (loses original offset info)
                        parsed_dt = parsed_dt.replace(tzinfo=None)

                    pop_logger.debug(f"Successfully parsed datetime {original_value_repr} using format '{fmt}' -> {parsed_dt}")
                    return parsed_dt
                except ValueError:
                    continue # Try next format
            if parsed_dt is None:
                pop_logger.warning(f"Could not parse datetime string {original_value_repr} with known formats.")
                return default

        # Add other types like date, time if needed based on XSD_TYPE_MAP usage
        if target_type is date:
             return date.fromisoformat(value_str) # Assumes YYYY-MM-DD
        if target_type is time:
             return time.fromisoformat(value_str) # Assumes HH:MM:SS[.ffffff][+/-HH:MM]

        # General cast attempt for types not explicitly handled above
        return target_type(value_str)
    except (ValueError, TypeError, InvalidOperation) as e:
        pop_logger.warning(f"Failed to cast {original_value_repr} to {target_type.__name__}: {e}. Returning default: {default}")
        return default
    except Exception as e:
        pop_logger.error(f"Unexpected error casting {original_value_repr} to {target_type.__name__}: {e}", exc_info=False)
        return default


def get_or_create_individual(onto_class, individual_name_base, onto, add_labels=None):
    """
    Gets an individual if it exists, otherwise creates it.
    Uses a naming convention incorporating the class name to reduce cross-class collisions.
    Args:
        onto_class: The owlready2 class object.
        individual_name_base: The base name derived from data (e.g., ID, description).
        onto: The owlready2 ontology object.
        add_labels (list): Optional list of strings to add as rdfs:label.
    Returns:
        The owlready2 individual object or None if creation failed.
    """
    if not individual_name_base:
        pop_logger.warning(f"Cannot get/create individual with empty base name for class {onto_class.name}")
        return None

    # 1. Sanitize the base name
    # Replace problematic characters (spaces, punctuation not allowed in IRIs)
    # Basic sanitization - adjust regex as needed for your specific data patterns
    safe_base = re.sub(r'\s+', '_', str(individual_name_base).strip())
    safe_base = re.sub(r'[^\w\-.]', '', safe_base) # Keep word chars, hyphen, period

    if not safe_base: # Handle cases where name becomes empty after sanitization
        # Generate a fallback using hash - less readable but unique
        fallback_hash = abs(hash(str(individual_name_base))) # Use abs for positivity
        safe_base = f"UnnamedData_{fallback_hash}"
        pop_logger.warning(f"Sanitized name for '{individual_name_base}' became empty. Using fallback: {safe_base}")

    # 2. Create the class-specific, sanitized name for the individual's IRI fragment
    # Prepending class name helps avoid clashes like having an Equipment '123' and a Material '123'
    # Using CamelCase for class name is common, ensure consistency
    final_name = f"{onto_class.name}_{safe_base}"

    # 3. Check if individual with this final name already exists
    individual = onto[final_name]

    if individual:
        # Check if the existing individual is of the correct type
        if isinstance(individual, onto_class):
            pop_logger.debug(f"Retrieved existing individual: {individual.iri} of class {onto_class.name}")
            # Optionally add labels even if retrieved
            if add_labels:
                for lbl in add_labels:
                    if lbl and str(lbl) not in individual.label:
                         individual.label.append(str(lbl))
            return individual
        else:
            # This should be rare with the class name prefix, but possible if manually created
            pop_logger.error(f"IRI collision: Individual '{final_name}' ({individual.iri}) exists but is not of expected type {onto_class.name}. It has type(s): {individual.is_a}. Cannot proceed reliably.")
            # Raise error or return None - Raising is safer to prevent data corruption
            raise TypeError(f"IRI collision: {final_name} exists with wrong type.")
            # return None

    # 4. Create the new individual if it doesn't exist
    try:
        pop_logger.debug(f"Creating new individual '{final_name}' of class {onto_class.name}")
        new_individual = onto_class(final_name, namespace=onto) # Ensure it's created in the target ontology

        # Add labels if provided
        if add_labels:
            for lbl in add_labels:
                 if lbl: new_individual.label.append(str(lbl))

        return new_individual
    except Exception as e:
        pop_logger.error(f"Failed to create individual '{final_name}' of class {onto_class.name}: {e}")
        return None


# --- Main Population Function ---

def populate_ontology_from_data(onto, data_rows, defined_classes, defined_properties):
    """
    Populates the ontology with individuals and relations from data rows.

    Args:
        onto: The owlready2 ontology object.
        data_rows: A list of dictionaries (rows from data CSV).
        defined_classes: Dictionary mapping class names to owlready2 class objects.
        defined_properties: Dictionary mapping property names to owlready2 property objects.
    
    Returns:
        int: The number of failed rows.
    """
    pop_logger.info(f"Starting ontology population with {len(data_rows)} data rows.")

    # Track equipment class sequence positions for verification
    equipment_class_positions = {}

    # --- Get Class Objects ---
    # Fetch classes needed for population, checking they were defined
    cls_Plant = defined_classes.get("Plant")
    cls_Area = defined_classes.get("Area")
    cls_ProcessCell = defined_classes.get("ProcessCell")
    cls_ProductionLine = defined_classes.get("ProductionLine")
    cls_Equipment = defined_classes.get("Equipment")
    cls_EquipmentClass = defined_classes.get("EquipmentClass")
    cls_Material = defined_classes.get("Material")
    cls_ProductionRequest = defined_classes.get("ProductionRequest")
    cls_EventRecord = defined_classes.get("EventRecord")
    cls_TimeInterval = defined_classes.get("TimeInterval")
    cls_Shift = defined_classes.get("Shift")
    cls_OperationalState = defined_classes.get("OperationalState")
    cls_OperationalReason = defined_classes.get("OperationalReason")
    # Add other classes like Personnel, Capability etc. if needed

    essential_classes_map = {
        "Plant": cls_Plant, "Area": cls_Area, "ProcessCell": cls_ProcessCell,
        "ProductionLine": cls_ProductionLine, "Equipment": cls_Equipment,
        "EquipmentClass": cls_EquipmentClass, "Material": cls_Material,
        "ProductionRequest": cls_ProductionRequest, "EventRecord": cls_EventRecord,
        "TimeInterval": cls_TimeInterval, "Shift": cls_Shift,
        "OperationalState": cls_OperationalState, "OperationalReason": cls_OperationalReason
    }
    missing_classes = [name for name, cls in essential_classes_map.items() if not cls]
    if missing_classes:
        pop_logger.error(f"Cannot proceed with population. Missing essential classes definitions: {missing_classes}")
        return len(data_rows) # Return all rows as failed

    # --- Get Property Objects ---
    # Fetch properties, checking they were defined. Use None if missing, handle downstream.
    prop_map = {}
    prop_names = [
        # IDs & Names (Data Props)
        "plantId", "areaId", "processCellId", "lineId", "equipmentId", "equipmentName",
        "equipmentClassId", "equipmentModel", "complexity", "alternativeModel",
        "materialId", "materialDescription", "sizeType", "materialUOM", "standardUOM",
        "targetProductUOM", "conversionFactor", "requestId", "requestDescription",
        "requestRate", "requestRateUOM", "startTime", "endTime", "shiftId",
        "shiftStartTime", "shiftEndTime", "shiftDurationMinutes", "rampUpFlag",
        "operationType", "reportedDurationMinutes", "businessExternalTimeMinutes",
        "plantAvailableTimeMinutes", "effectiveRuntimeMinutes", "plantDecisionTimeMinutes",
        "productionAvailableTimeMinutes", "stateDescription", "reasonDescription",
        "altReasonDescription", "downtimeDriver", "changeoverType", "defaultSequencePosition",
        # Relationships (Object Props - verify these names match your spec exactly!)
        "memberOfClass", "locatedInPlant", "partOfArea", "locatedInProcessCell",
        "isPartOfProductionLine", "involvesResource", "associatedWithProductionRequest",
        "usesMaterial", "occursDuring", "duringShift", "eventHasState", "eventHasReason",
        "isUpstreamOf", "isDownstreamOf"
    ]
    
    # Define which properties are functional (should be directly assigned vs. appended)
    functional_properties = {
        # Datatype properties (generally functional)
        "plantId", "areaId", "processCellId", "lineId", "equipmentId", "equipmentClassId",
        "equipmentModel", "materialId", "materialUOM", "standardUOM", "targetProductUOM",
        "conversionFactor", "requestId", "requestRate", "requestRateUOM", "startTime", 
        "endTime", "shiftId", "shiftStartTime", "shiftEndTime", "shiftDurationMinutes", 
        "rampUpFlag", "reportedDurationMinutes", "businessExternalTimeMinutes",
        "plantAvailableTimeMinutes", "effectiveRuntimeMinutes", "plantDecisionTimeMinutes",
        "productionAvailableTimeMinutes", "defaultSequencePosition",
        
        # Object properties marked as Functional in the spec
        "memberOfClass", "locatedInPlant", "partOfArea", "locatedInProcessCell", 
        "isPartOfProductionLine", "occursDuring", "duringShift", "eventHasState", 
        "eventHasReason"
    }
    
    essential_prop_names = { # Define props critical for basic structure/linking
         "equipmentId", "lineId", "involvesResource", "occursDuring", "startTime"
         # Add more as needed
    }

    missing_essential_props = []
    for name in prop_names:
        prop_map[name] = defined_properties.get(name)
        if not prop_map[name] and name in essential_prop_names:
             missing_essential_props.append(name)
        elif not prop_map[name]:
             pop_logger.warning(f"Property '{name}' not found in ontology definition. Population using this property will be skipped.")

    if missing_essential_props:
        pop_logger.error(f"Cannot reliably proceed with population. Missing essential properties definitions: {missing_essential_props}")
        return len(data_rows) # Return all rows as failed


    # --- Process Data Rows ---
    with onto: # Use the ontology context for creating individuals
        successful_rows = 0
        failed_rows = 0
        for i, row in enumerate(data_rows):
            row_num = i + 1 # 1-based index for logging
            pop_logger.debug(f"--- Processing Row {row_num} ---")
            try:
                # --- Create / Retrieve Core Asset Hierarchy Individuals ---
                plant_id = safe_cast(row.get('PLANT'), str)
                plant_labels = [plant_id]
                plant_ind = get_or_create_individual(cls_Plant, plant_id, onto, add_labels=plant_labels)
                if plant_ind and prop_map["plantId"]: 
                    plant_ind.plantId = plant_id

                area_id = safe_cast(row.get('GH_FOCUSFACTORY'), str) # Using FocusFactory as Area ID based on spec assumption
                area_unique_base = f"{plant_id}_{area_id}"
                area_labels = [area_id]
                area_ind = get_or_create_individual(cls_Area, area_unique_base, onto, add_labels=area_labels)
                if area_ind:
                    if prop_map["areaId"]: 
                        area_ind.areaId = area_id
                    # Add relationship: Area locatedInPlant Plant
                    prop_locatedInPlant = prop_map.get("locatedInPlant")
                    if prop_locatedInPlant and plant_ind:
                        if plant_ind not in prop_locatedInPlant[area_ind]:
                            prop_locatedInPlant[area_ind].append(plant_ind)

                pcell_id = safe_cast(row.get('PHYSICAL_AREA'), str) # Using PhysicalArea as ProcessCell ID assumption
                pcell_unique_base = f"{area_unique_base}_{pcell_id}"
                pcell_labels = [pcell_id]
                pcell_ind = get_or_create_individual(cls_ProcessCell, pcell_unique_base, onto, add_labels=pcell_labels)
                if pcell_ind:
                    if prop_map["processCellId"]: 
                        pcell_ind.processCellId = pcell_id
                    # Add relationship: ProcessCell partOfArea Area
                    prop_partOfArea = prop_map.get("partOfArea")
                    if prop_partOfArea and area_ind:
                        if area_ind not in prop_partOfArea[pcell_ind]:
                            prop_partOfArea[pcell_ind].append(area_ind)

                line_id = safe_cast(row.get('LINE_NAME'), str)
                line_unique_base = f"{pcell_unique_base}_{line_id}"
                line_labels = [line_id]
                line_ind = get_or_create_individual(cls_ProductionLine, line_unique_base, onto, add_labels=line_labels)
                if line_ind:
                    if prop_map["lineId"]: 
                        line_ind.lineId = line_id
                    # Add relationship: ProductionLine locatedInProcessCell ProcessCell
                    prop_locatedInProcessCell = prop_map.get("locatedInProcessCell")
                    if prop_locatedInProcessCell and pcell_ind:
                        if pcell_ind not in prop_locatedInProcessCell[line_ind]:
                            prop_locatedInProcessCell[line_ind].append(pcell_ind)


                # --- Identify the Resource (Line or Equipment) for the Event ---
                eq_id_raw = row.get('EQUIPMENT_ID')
                eq_id_str = safe_cast(eq_id_raw, str) # Keep as string for ID/lookup
                eq_name = safe_cast(row.get('EQUIPMENT_NAME'), str)
                eq_type = safe_cast(row.get('EQUIPMENT_TYPE'), str) # 'Line' or 'Equipment'

                equipment_ind = None
                resource_individual = None # This will hold the individual linked by EventRecord
                resource_base_id = None  # Base ID used for naming related individuals (like Event, TimeInterval)

                if eq_type == 'Line' and line_ind:
                    resource_individual = line_ind
                    resource_base_id = line_unique_base # Use the unique line base name
                    pop_logger.debug(f"Row {row_num}: Identified as Line record for: {line_id}")

                elif eq_type == 'Equipment' and eq_id_str and cls_Equipment:
                    # Create Equipment individual
                    eq_unique_base = eq_id_str # Assume equipment ID is unique enough globally or within plant context
                    eq_labels = [eq_name, f"ID:{eq_id_str}"]
                    equipment_ind = get_or_create_individual(cls_Equipment, eq_unique_base, onto, add_labels=eq_labels)
                    if equipment_ind:
                        resource_individual = equipment_ind
                        resource_base_id = f"Eq_{eq_unique_base}" # Prefix for clarity in related names

                        # Set Equipment properties
                        if prop_map["equipmentId"]:
                            equipment_ind.equipmentId = eq_id_str
                        if prop_map["equipmentName"] and eq_name: 
                            equipment_ind.equipmentName.append(eq_name)
                        if prop_map["equipmentModel"]:
                            model = safe_cast(row.get('EQUIPMENT_MODEL'), str)
                            if model: 
                                equipment_ind.equipmentModel = model
                        if prop_map["complexity"]:
                            complexity = safe_cast(row.get('COMPLEXITY'), str)
                            if complexity: 
                                equipment_ind.complexity.append(complexity)
                        if prop_map["alternativeModel"]:
                            alt_model = safe_cast(row.get('MODEL'), str) # Assuming 'MODEL' is alt model? Check spec.
                            if alt_model: 
                                equipment_ind.alternativeModel.append(alt_model)

                        # Link Equipment to ProductionLine
                        prop_isPartOfProductionLine = prop_map.get("isPartOfProductionLine")
                        if prop_isPartOfProductionLine and line_ind:
                            if line_ind not in prop_isPartOfProductionLine[equipment_ind]:
                                prop_isPartOfProductionLine[equipment_ind].append(line_ind)

                        # Parse and link EquipmentClass
                        if cls_EquipmentClass:
                            eq_class_name = parse_equipment_class(eq_name)
                            if eq_class_name:
                                eq_class_labels = [eq_class_name]
                                eq_class_ind = get_or_create_individual(cls_EquipmentClass, eq_class_name, onto, add_labels=eq_class_labels)
                                if eq_class_ind:
                                    if prop_map["equipmentClassId"]: 
                                        eq_class_ind.equipmentClassId = eq_class_name
                                    
                                    # Link Equipment to EquipmentClass
                                    prop_memberOfClass = prop_map.get("memberOfClass")
                                    if prop_memberOfClass and equipment_ind and eq_class_ind:
                                        if eq_class_ind not in prop_memberOfClass[equipment_ind]:
                                            prop_memberOfClass[equipment_ind].append(eq_class_ind)
                                    
                                    # Set default sequence position if property exists and not already set
                                    prop_defaultSequencePosition = prop_map.get("defaultSequencePosition")
                                    if prop_defaultSequencePosition:
                                        pop_logger.debug(f"Checking default sequence position for equipment class: {eq_class_name}")
                                        default_pos = DEFAULT_EQUIPMENT_SEQUENCE.get(eq_class_name)
                                        if default_pos is not None:
                                            existing_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
                                            if existing_pos is None:
                                                setattr(eq_class_ind, "defaultSequencePosition", default_pos)
                                                pop_logger.debug(f"Set default sequence position for {eq_class_name} to {default_pos}")
                                                equipment_class_positions[eq_class_name] = default_pos
                                            elif existing_pos != default_pos:
                                                pop_logger.warning(f"Equipment class {eq_class_name} already has sequence position {existing_pos}, different from default {default_pos}")
                                                equipment_class_positions[eq_class_name] = existing_pos
                                            else:
                                                pop_logger.debug(f"Equipment class {eq_class_name} already has correct sequence position {existing_pos}")
                                                equipment_class_positions[eq_class_name] = existing_pos
                                        else:
                                            pop_logger.info(f"No default sequence position found in mapping for equipment class: {eq_class_name}")
                                            # Check if it already has a position set
                                            existing_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
                                            if existing_pos is not None:
                                                equipment_class_positions[eq_class_name] = existing_pos
                                                pop_logger.debug(f"Equipment class {eq_class_name} has manually set sequence position: {existing_pos}")
                            else:
                                pop_logger.warning(f"Row {row_num}: Could not parse EquipmentClass from EQUIPMENT_NAME: {eq_name}")

                        pop_logger.debug(f"Row {row_num}: Identified as Equipment record for: {eq_id_str}")
                    else:
                         pop_logger.error(f"Row {row_num}: Failed to create Equipment individual for ID '{eq_id_str}'.")
                         # Cannot proceed with this row if resource cannot be determined
                         raise ValueError("Failed to create Equipment individual.")

                else:
                    pop_logger.warning(f"Row {row_num}: Could not determine resource. EQUIPMENT_TYPE='{eq_type}', EQUIPMENT_ID='{eq_id_raw}', LINE_NAME='{line_id}'. Skipping row.")
                    failed_rows += 1
                    continue # Skip if we can't identify the main resource

                if not resource_base_id:
                     pop_logger.error(f"Row {row_num}: Internal error - resource_base_id not set. Skipping row.")
                     failed_rows += 1
                     continue

                # --- Create Material Individual ---
                mat_id = safe_cast(row.get('MATERIAL_ID'), str)
                mat_ind = None
                if mat_id and cls_Material:
                    mat_desc = safe_cast(row.get('SHORT_MATERIAL_ID'), str) # Use short ID as description? Check spec.
                    mat_labels = [mat_id, mat_desc]
                    mat_ind = get_or_create_individual(cls_Material, mat_id, onto, add_labels=mat_labels)
                    if mat_ind:
                        # Set Material properties
                        if prop_map["materialId"]: 
                            mat_ind.materialId = mat_id
                        if prop_map["materialDescription"] and mat_desc: 
                            mat_ind.materialDescription.append(mat_desc)
                        if prop_map["sizeType"]:
                             size = safe_cast(row.get('SIZE_TYPE'), str)
                             if size: 
                                 mat_ind.sizeType.append(size)
                        if prop_map["materialUOM"]:
                            material_uom = safe_cast(row.get('MATERIAL_UOM'), str)
                            if material_uom: 
                                mat_ind.materialUOM = material_uom
                        # Handle combined UOM columns if necessary (check spec logic)
                        uom_st = safe_cast(row.get('UOM_ST'), str) or safe_cast(row.get('UOM_ST_SAP'), str)
                        if prop_map["standardUOM"] and uom_st: 
                            mat_ind.standardUOM = uom_st
                        if prop_map["targetProductUOM"]:
                             tp_uom = safe_cast(row.get('TP_UOM'), str)
                             if tp_uom: 
                                 mat_ind.targetProductUOM = tp_uom
                        if prop_map["conversionFactor"]:
                             factor = safe_cast(row.get('PRIMARY_CONV_FACTOR'), float)
                             if factor is not None: 
                                 mat_ind.conversionFactor = factor

                # --- Create Production Request Individual ---
                req_id = safe_cast(row.get('PRODUCTION_ORDER_ID'), str)
                req_ind = None
                if req_id and cls_ProductionRequest:
                    req_desc = safe_cast(row.get('PRODUCTION_ORDER_DESC'), str)
                    req_labels = [req_desc, f"ID:{req_id}"]
                    req_ind = get_or_create_individual(cls_ProductionRequest, req_id, onto, add_labels=req_labels)
                    if req_ind:
                        if prop_map["requestId"]: 
                            req_ind.requestId = req_id
                        if prop_map["requestDescription"] and req_desc: 
                            req_ind.requestDescription.append(req_desc)
                        if prop_map["requestRate"]:
                             rate = safe_cast(row.get('PRODUCTION_ORDER_RATE'), float)
                             if rate is not None: 
                                 req_ind.requestRate = rate
                        if prop_map["requestRateUOM"]:
                             rate_uom = safe_cast(row.get('PRODUCTION_ORDER_UOM'), str)
                             if rate_uom: 
                                 req_ind.requestRateUOM = rate_uom
                        
                        # Link ProductionRequest to Material if needed
                        prop_usesMaterial = prop_map.get("usesMaterial")
                        if prop_usesMaterial and mat_ind:
                            if mat_ind not in prop_usesMaterial[req_ind]:
                                prop_usesMaterial[req_ind].append(mat_ind)


                # --- Create Shift Individual ---
                shift_name = safe_cast(row.get('SHIFT_NAME'), str)
                shift_ind = None
                if shift_name and cls_Shift:
                    # Assume shift name is unique enough as base ID
                    shift_labels = [shift_name]
                    shift_ind = get_or_create_individual(cls_Shift, shift_name, onto, add_labels=shift_labels)
                    if shift_ind:
                        # Populate shift details (only once needed per shift, but safe_cast/assignment handles repeats)
                        if prop_map["shiftId"]: 
                            shift_ind.shiftId = shift_name
                        if prop_map["shiftStartTime"]:
                            st = safe_cast(row.get('SHIFT_START_DATE_LOC'), datetime)
                            if st: 
                                shift_ind.shiftStartTime = st
                        if prop_map["shiftEndTime"]:
                            et = safe_cast(row.get('SHIFT_END_DATE_LOC'), datetime)
                            if et: 
                                shift_ind.shiftEndTime = et
                        if prop_map["shiftDurationMinutes"]:
                            dur = safe_cast(row.get('SHIFT_DURATION_MIN'), float)
                            if dur is not None: 
                                shift_ind.shiftDurationMinutes = dur


                # --- Create Operational State and Reason Individuals ---
                # First create OperationalState
                state_desc = safe_cast(row.get('UTIL_STATE_DESCRIPTION'), str)
                state_ind = None
                if state_desc and cls_OperationalState:
                    state_labels = [state_desc]
                    # Create unique state instance based on description
                    state_ind = get_or_create_individual(cls_OperationalState, state_desc, onto, add_labels=state_labels)
                    if state_ind:
                        # Use append for non-functional properties
                        if prop_map["stateDescription"] and state_desc:
                            state_ind.stateDescription.append(state_desc)
                
                # Then create OperationalReason as a separate individual
                reason_desc = safe_cast(row.get('UTIL_REASON_DESCRIPTION'), str)
                reason_ind = None
                if reason_desc and cls_OperationalReason:
                    reason_labels = [reason_desc]
                    # Create unique reason instance based on description
                    reason_ind = get_or_create_individual(cls_OperationalReason, reason_desc, onto, add_labels=reason_labels)
                    if reason_ind:
                        # Add ReasonDescription (non-functional)
                        if prop_map["reasonDescription"] and reason_desc:
                            reason_ind.reasonDescription.append(reason_desc)
                        
                        # Handle AltReasonDescription with language tag based on plant country
                        if prop_map["altReasonDescription"]:
                            alt_reason = safe_cast(row.get('UTIL_ALT_LANGUAGE_REASON'), str)
                            if alt_reason:
                                # Get the plant country to determine language
                                plant_country = safe_cast(row.get('PLANT_COUNTRY_DESCRIPTION'), str)
                                # Map country to language tag
                                lang_tag = COUNTRY_TO_LANGUAGE.get(plant_country, DEFAULT_LANGUAGE)
                                if lang_tag:
                                    # Create localized string with language tag
                                    try:
                                        alt_reason_locstr = locstr(alt_reason, lang=lang_tag)
                                        # Use append for non-functional property
                                        reason_ind.altReasonDescription.append(alt_reason_locstr)
                                        pop_logger.debug(f"Added localized reason description '{alt_reason}' with language '{lang_tag}'")
                                    except Exception as e:
                                        pop_logger.warning(f"Failed to create locstr for alt reason '{alt_reason}': {e}")
                                        # Fallback to plain string if locstr fails
                                        reason_ind.altReasonDescription.append(alt_reason)
                                else:
                                    # No language mapping found, use plain string
                                    pop_logger.warning(f"No language mapping for country '{plant_country}', using plain string")
                                    reason_ind.altReasonDescription.append(alt_reason)
                        
                        # Handle DowntimeDriver (non-functional)
                        if prop_map["downtimeDriver"]:
                            dt_driver = safe_cast(row.get('DOWNTIME_DRIVER'), str)
                            if dt_driver:
                                # Use append for non-functional property
                                reason_ind.downtimeDriver.append(dt_driver)
                        
                        # Handle ChangeoverType (non-functional)
                        if prop_map["changeoverType"]:
                            # Handle combined CO_TYPE columns (check spec logic)
                            co_type = safe_cast(row.get('CO_TYPE'), str) or safe_cast(row.get('CO_ORIGINAL_TYPE'), str)
                            if co_type:
                                # Use append for non-functional property
                                reason_ind.changeoverType.append(co_type)


                # --- Create Time Interval ---
                start_time = safe_cast(row.get('JOB_START_TIME_LOC'), datetime)
                end_time = safe_cast(row.get('JOB_END_TIME_LOC'), datetime)
                time_interval_ind = None
                if start_time and cls_TimeInterval:
                    # Create a unique TimeInterval for each event record using resource and start time
                    # Format datetime for IRI compatibility (basic example)
                    start_time_str = start_time.strftime('%Y%m%dT%H%M%S%f')[:-3] # Milliseconds precision
                    interval_base = f"{resource_base_id}_{start_time_str}_{row_num}" # Add row num for absolute uniqueness
                    interval_labels = [f"Interval for {resource_base_id} at {start_time}"]
                    time_interval_ind = get_or_create_individual(cls_TimeInterval, interval_base, onto, add_labels=interval_labels)
                    if time_interval_ind:
                        if prop_map["startTime"]: 
                            time_interval_ind.startTime = start_time
                        if prop_map["endTime"] and end_time: 
                            time_interval_ind.endTime = end_time
                        # Calculate duration? Spec doesn't require it directly on TimeInterval here
                    else:
                         pop_logger.error(f"Row {row_num}: Failed to create TimeInterval individual.")
                         # Decide if this is fatal for the row
                         raise ValueError("Failed to create TimeInterval.")
                elif not start_time:
                     pop_logger.error(f"Row {row_num}: Missing JOB_START_TIME_LOC, cannot create TimeInterval or EventRecord. Skipping row.")
                     failed_rows += 1
                     continue # Cannot create event without start time

                # --- Create Event Record Individual ---
                # Use the same base name as the time interval for association
                event_record_base = interval_base # Link event name to interval name
                event_labels = [f"Event for {resource_base_id} at {start_time}"]
                event_ind = get_or_create_individual(cls_EventRecord, event_record_base, onto, add_labels=event_labels)

                if not event_ind:
                    pop_logger.error(f"Row {row_num}: Failed to create EventRecord individual. Skipping row.")
                    failed_rows += 1
                    continue

                # --- Populate EventRecord Data Properties ---
                if prop_map["operationType"]:
                     op_type = safe_cast(row.get('OPERA_TYPE'), str)
                     if op_type: 
                         # Use append for non-functional property
                         event_ind.operationType.append(op_type)
                if prop_map["rampUpFlag"]:
                     # Default to False if missing/invalid
                     ramp_flag = safe_cast(row.get('RAMPUP_FLAG'), bool, default=False)
                     # Direct assignment for functional property
                     event_ind.rampUpFlag = ramp_flag

                # Time Metrics (handle units carefully based on spec)
                # Assuming properties expect minutes
                total_time_min = safe_cast(row.get('TOTAL_TIME'), float) # Assumed minutes
                if prop_map["reportedDurationMinutes"] and total_time_min is not None:
                    event_ind.reportedDurationMinutes = total_time_min

                # Assign other time metrics if properties exist
                time_metric_cols = {
                    "businessExternalTimeMinutes": "BUSINESS_EXTERNAL_TIME",
                    "plantAvailableTimeMinutes": "PLANT_AVAILABLE_TIME",
                    "effectiveRuntimeMinutes": "EFFECTIVE_RUNTIME",
                    "plantDecisionTimeMinutes": "PLANT_DECISION_TIME",
                    "productionAvailableTimeMinutes": "PRODUCTION_AVAILABLE_TIME"
                }
                for prop_name, col_name in time_metric_cols.items():
                    if prop_map[prop_name]:
                         val = safe_cast(row.get(col_name), float)
                         if val is not None:
                             # Direct assignment for functional properties
                             setattr(event_ind, prop_name, val)


                # --- Link EventRecord to other Individuals (Object Properties) ---
                # Using property indexing for safer non-functional object property assignments
                # and direct assignment for functional properties
                
                # Link to resource (Line or Equipment) - involvesResource might be functional or not per spec
                prop_involvesResource = prop_map.get("involvesResource")
                if prop_involvesResource and resource_individual:
                    if "involvesResource" in functional_properties:
                        # Direct assignment if functional
                        event_ind.involvesResource = resource_individual
                        pop_logger.debug(f"Set functional property involvesResource for {event_ind.name} to {resource_individual.name}")
                    else:
                        # Append if non-functional
                        if resource_individual not in prop_involvesResource[event_ind]:
                            prop_involvesResource[event_ind].append(resource_individual)
                
                # Link to ProductionRequest - associatedWithProductionRequest
                prop_associatedWithProductionRequest = prop_map.get("associatedWithProductionRequest")
                if prop_associatedWithProductionRequest and req_ind:
                    if "associatedWithProductionRequest" in functional_properties:
                        # Direct assignment if functional
                        event_ind.associatedWithProductionRequest = req_ind
                    else:
                        # Append if non-functional
                        if req_ind not in prop_associatedWithProductionRequest[event_ind]:
                            prop_associatedWithProductionRequest[event_ind].append(req_ind)
                
                # Link to Material - usesMaterial
                prop_usesMaterial = prop_map.get("usesMaterial")
                if prop_usesMaterial and mat_ind:
                    if "usesMaterial" in functional_properties:
                        # Direct assignment if functional
                        event_ind.usesMaterial = mat_ind
                    else:
                        # Append if non-functional
                        if mat_ind not in prop_usesMaterial[event_ind]:
                            prop_usesMaterial[event_ind].append(mat_ind)
                
                # Link to TimeInterval - occursDuring (functional per spec)
                prop_occursDuring = prop_map.get("occursDuring")
                if prop_occursDuring and time_interval_ind:
                    if "occursDuring" in functional_properties:
                        # Direct assignment for functional property
                        event_ind.occursDuring = time_interval_ind
                        pop_logger.debug(f"Set functional property occursDuring for {event_ind.name} to {time_interval_ind.name}")
                    else:
                        # Append if non-functional (per spec)
                        if time_interval_ind not in prop_occursDuring[event_ind]:
                            prop_occursDuring[event_ind].append(time_interval_ind)
                
                # Link to Shift - duringShift (functional per spec)
                prop_duringShift = prop_map.get("duringShift")
                if prop_duringShift and shift_ind:
                    if "duringShift" in functional_properties:
                        # Direct assignment for functional property
                        event_ind.duringShift = shift_ind
                        pop_logger.debug(f"Set functional property duringShift for {event_ind.name} to {shift_ind.name}")
                    else:
                        # Append if non-functional (per spec)
                        if shift_ind not in prop_duringShift[event_ind]:
                            prop_duringShift[event_ind].append(shift_ind)
                
                # Link to OperationalState - eventHasState (functional per spec)
                prop_eventHasState = prop_map.get("eventHasState")
                if prop_eventHasState and state_ind:
                    if "eventHasState" in functional_properties:
                        # Direct assignment for functional property
                        event_ind.eventHasState = state_ind
                        pop_logger.debug(f"Set functional property eventHasState for {event_ind.name} to {state_ind.name}")
                    else:
                        # Append if non-functional (per spec)
                        if state_ind not in prop_eventHasState[event_ind]:
                            prop_eventHasState[event_ind].append(state_ind)
                
                # Link to OperationalReason - eventHasReason (functional per spec)
                prop_eventHasReason = prop_map.get("eventHasReason")
                if prop_eventHasReason and reason_ind:
                    if "eventHasReason" in functional_properties:
                        # Direct assignment for functional property
                        event_ind.eventHasReason = reason_ind
                        pop_logger.debug(f"Set functional property eventHasReason for {event_ind.name} to {reason_ind.name}")
                    else:
                        # Append if non-functional (per spec)
                        if reason_ind not in prop_eventHasReason[event_ind]:
                            prop_eventHasReason[event_ind].append(reason_ind)
                
                # Add links to Personnel, ProcessSegment etc. if data/properties exist

                successful_rows += 1
                pop_logger.debug(f"--- Successfully Processed Row {row_num} ---")

            except Exception as e:
                failed_rows += 1
                pop_logger.error(f"Error processing data row {row_num}: {row}")
                pop_logger.exception("Exception details:") # Log traceback for debugging

    # Log equipment class sequence position summary
    if equipment_class_positions:
        pop_logger.info("--- Equipment Class Sequence Position Summary ---")
        # Sort by position value for clearer output
        sorted_classes = sorted(equipment_class_positions.items(), key=lambda x: x[1])
        for eq_class, position in sorted_classes:
            pop_logger.info(f"Equipment Class: {eq_class} - Sequence Position: {position}")
        pop_logger.info(f"Total equipment classes with sequence positions: {len(equipment_class_positions)}")
        
        # Use sequence positions to establish upstream/downstream relationships
        setup_equipment_sequence_relationships(onto, equipment_class_positions, defined_classes, prop_map)
        
        # Set up instance-level relationships between equipment within the same line
        setup_equipment_instance_relationships(onto, defined_classes, prop_map, equipment_class_positions)
    else:
        pop_logger.warning("No equipment classes with sequence positions were processed")

    # Force the report to stdout regardless of logging configuration
    if equipment_class_positions:
        print("\n=== EQUIPMENT CLASS SEQUENCE POSITION REPORT ===")
        sorted_classes = sorted(equipment_class_positions.items(), key=lambda x: x[1])
        for eq_class, position in sorted_classes:
            print(f"Equipment Class: {eq_class} - Sequence Position: {position}")
        print(f"Total: {len(equipment_class_positions)} equipment classes")
    else:
        print("No equipment classes with sequence positions were processed")

    pop_logger.info(f"Ontology population complete. Successfully processed {successful_rows} rows, failed to process {failed_rows} rows.")
    return failed_rows  # Return the count of failed rows

def setup_equipment_sequence_relationships(onto, equipment_class_positions, defined_classes, prop_map):
    """
    Establish upstream/downstream relationships between equipment classes based on their sequence positions.
    
    Args:
        onto: The ontology object
        equipment_class_positions: Dictionary mapping equipment class names to their sequence positions
        defined_classes: Dictionary of defined class objects
        prop_map: Dictionary mapping property names to property objects
    """
    pop_logger.info("Setting up equipment sequence relationships based on position values...")
    
    # Get the relevant properties
    prop_isUpstreamOf = prop_map.get("isUpstreamOf")
    prop_isDownstreamOf = prop_map.get("isDownstreamOf")
    
    if not prop_isUpstreamOf or not prop_isDownstreamOf:
        pop_logger.error("Cannot establish equipment sequence relationships: isUpstreamOf and/or isDownstreamOf properties not found")
        return
    
    # Sort equipment classes by position
    sorted_classes = sorted(equipment_class_positions.items(), key=lambda x: x[1])
    
    if len(sorted_classes) < 2:
        pop_logger.warning("Not enough equipment classes with sequence positions to establish relationships")
        return
    
    # Create a dictionary to map class names to their individuals
    eqclass_individuals = {}
    for class_name, _ in sorted_classes:
        # Ensure the class exists in defined_classes
        if class_name not in defined_classes:
            pop_logger.warning(f"Equipment class '{class_name}' not found in defined classes")
            continue
            
        # Look up the class individual that was created
        eqclass_ind = None
        for ind in onto.search(type=defined_classes["EquipmentClass"]):
            if getattr(ind, "equipmentClassId", None) == class_name:
                eqclass_ind = ind
                break
                
        if not eqclass_ind:
            pop_logger.warning(f"No individual found for equipment class '{class_name}'")
            continue
            
        eqclass_individuals[class_name] = eqclass_ind
    
    # Create upstream/downstream relationships based on sequence order
    relationships_created = 0
    with onto:
        for i in range(len(sorted_classes) - 1):
            upstream_class_name, _ = sorted_classes[i]
            downstream_class_name, _ = sorted_classes[i + 1]
            
            upstream_ind = eqclass_individuals.get(upstream_class_name)
            downstream_ind = eqclass_individuals.get(downstream_class_name)
            
            if not upstream_ind or not downstream_ind:
                continue
                
            # Set upstream/downstream relationships
            if downstream_ind not in prop_isUpstreamOf[upstream_ind]:
                prop_isUpstreamOf[upstream_ind].append(downstream_ind)
                pop_logger.debug(f"Set {upstream_class_name} isUpstreamOf {downstream_class_name}")
                relationships_created += 1
                
            # The inverse relationship should be handled automatically if setup correctly
            # But check to be safe
            if upstream_ind not in prop_isDownstreamOf[downstream_ind]:
                pop_logger.debug(f"Checking inverse relationship {downstream_class_name} isDownstreamOf {upstream_class_name}")
    
    pop_logger.info(f"Created {relationships_created} upstream/downstream relationships based on sequence positions")
    
    # Print relationship summary to stdout
    print("\n=== EQUIPMENT SEQUENCE RELATIONSHIP REPORT ===")
    print(f"Created {relationships_created} upstream/downstream relationships")
    for i in range(len(sorted_classes) - 1):
        upstream_class_name, _ = sorted_classes[i]
        downstream_class_name, _ = sorted_classes[i + 1]
        print(f"{upstream_class_name} → {downstream_class_name}")
    print(f"Total: {relationships_created} relationships")

def setup_equipment_instance_relationships(onto, defined_classes, prop_map, equipment_class_positions):
    """
    Establish upstream/downstream relationships between equipment instances within the same production line.
    This ensures that a Filler on Line A is only upstream of a Cartoner on Line A, not a Cartoner on Line B.
    
    Args:
        onto: The ontology object
        defined_classes: Dictionary of defined class objects
        prop_map: Dictionary mapping property names to property objects
        equipment_class_positions: Dictionary mapping equipment class names to their sequence positions
    """
    pop_logger.info("Setting up equipment instance relationships within production lines...")
    
    # Get the required classes and properties
    cls_Equipment = defined_classes.get("Equipment")
    cls_ProductionLine = defined_classes.get("ProductionLine")
    prop_isPartOfProductionLine = prop_map.get("isPartOfProductionLine")
    prop_memberOfClass = prop_map.get("memberOfClass")
    
    # Equipment-level isUpstreamOf and isDownstreamOf properties (instance relationships)
    # These are different from the class-level properties
    prop_equipment_isUpstreamOf = prop_map.get("isUpstreamOf") 
    prop_equipment_isDownstreamOf = prop_map.get("isDownstreamOf")
    
    if not all([cls_Equipment, cls_ProductionLine, prop_isPartOfProductionLine, 
               prop_memberOfClass, prop_equipment_isUpstreamOf, prop_equipment_isDownstreamOf]):
        pop_logger.error("Missing required classes or properties for equipment instance relationships")
        return
    
    # Sort equipment classes by position
    sorted_classes = sorted(equipment_class_positions.items(), key=lambda x: x[1])
    if len(sorted_classes) < 2:
        pop_logger.warning("Not enough equipment classes to establish instance relationships")
        return
    
    # Get all production lines
    production_lines = list(onto.search(type=cls_ProductionLine))
    if not production_lines:
        pop_logger.warning("No production lines found to establish equipment instance relationships")
        return
    
    # Dictionary to store equipment by line and class
    line_equipment_map = {}  # {line_id: {class_name: [equipment_instances]}}
    
    # Group equipment instances by line and class
    for equipment in onto.search(type=cls_Equipment):
        # Check which line this equipment belongs to
        equipment_lines = []
        if prop_isPartOfProductionLine and hasattr(equipment, "isPartOfProductionLine"):
            if isinstance(equipment.isPartOfProductionLine, list):
                equipment_lines = equipment.isPartOfProductionLine
            else:
                equipment_lines = [equipment.isPartOfProductionLine]
        
        # Skip equipment not assigned to any line
        if not equipment_lines:
            continue
            
        # Check which equipment class this equipment belongs to
        equipment_class = None
        if prop_memberOfClass and hasattr(equipment, "memberOfClass"):
            if isinstance(equipment.memberOfClass, list):
                if equipment.memberOfClass:  # Take first class if multiple
                    equipment_class = equipment.memberOfClass[0]
            else:
                equipment_class = equipment.memberOfClass
        
        # Skip equipment not assigned to any class
        if not equipment_class:
            continue
            
        # Get the class name
        class_name = getattr(equipment_class, "equipmentClassId", None)
        if not class_name or class_name not in equipment_class_positions:
            continue
        
        # Add equipment to line and class mapping
        for line in equipment_lines:
            line_id = getattr(line, "lineId", str(line))
            if line_id not in line_equipment_map:
                line_equipment_map[line_id] = {}
            if class_name not in line_equipment_map[line_id]:
                line_equipment_map[line_id][class_name] = []
            line_equipment_map[line_id][class_name].append(equipment)
    
    # Create instance-level relationships within each line
    total_relationships = 0
    line_relationship_counts = {}
    
    with onto:
        for line_id, class_equipment_map in line_equipment_map.items():
            line_relationships = 0
            pop_logger.debug(f"Processing equipment relationships for line: {line_id}")
            
            # For each pair of adjacent equipment classes in the sequence
            for i in range(len(sorted_classes) - 1):
                upstream_class_name, _ = sorted_classes[i]
                downstream_class_name, _ = sorted_classes[i + 1]
                
                # Skip if either class doesn't have equipment on this line
                if (upstream_class_name not in class_equipment_map or 
                    downstream_class_name not in class_equipment_map):
                    continue
                
                upstream_equipment = class_equipment_map[upstream_class_name]
                downstream_equipment = class_equipment_map[downstream_class_name]
                
                # Create relationships between all equipment of adjacent classes on this line
                for upstream_eq in upstream_equipment:
                    for downstream_eq in downstream_equipment:
                        # Check if relationship already exists
                        if downstream_eq not in prop_equipment_isUpstreamOf[upstream_eq]:
                            prop_equipment_isUpstreamOf[upstream_eq].append(downstream_eq)
                            line_relationships += 1
                            pop_logger.debug(f"Set equipment relationship: {upstream_eq.name} isUpstreamOf {downstream_eq.name} on line {line_id}")
            
            # Record relationships for this line
            line_relationship_counts[line_id] = line_relationships
            total_relationships += line_relationships
    
    # Print summary report
    if total_relationships > 0:
        pop_logger.info(f"Created {total_relationships} equipment instance relationships across {len(line_relationship_counts)} production lines")
        print("\n=== EQUIPMENT INSTANCE RELATIONSHIP REPORT ===")
        print(f"Created equipment instance relationships on {len(line_relationship_counts)} lines:")
        for line_id, count in line_relationship_counts.items():
            print(f"Line {line_id}: {count} equipment relationships")
        print(f"Total: {total_relationships} instance-level relationships")
    else:
        pop_logger.warning("No equipment instance relationships were created")
        print("\n=== EQUIPMENT INSTANCE RELATIONSHIP REPORT ===")
        print("No equipment instance relationships could be established")
        print("Possible reasons: equipment not assigned to lines or classes, or missing sequence positions")

#======================================================================#
#                  create_ontology.py Module Code                      #
#======================================================================#

def read_data(data_file_path):
    """Reads the operational data CSV file."""
    main_logger.info(f"Reading data file: {data_file_path}")
    data_rows = []
    try:
        # Use utf-8-sig to handle potential byte order mark (BOM) in CSV files
        with open(data_file_path, mode='r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            data_rows = list(reader) # Read all rows into memory
        main_logger.info(f"Successfully read {len(data_rows)} data rows.")
        return data_rows
    except FileNotFoundError:
        main_logger.error(f"Data file not found: {data_file_path}")
        raise
    except Exception as e:
        main_logger.error(f"Error reading data file {data_file_path}: {e}")
        raise

def generate_reasoning_report(onto, pre_stats, post_stats, inconsistent_classes, 
                            inferred_hierarchy, inferred_properties, inferred_individuals):
    """
    Generates a structured report from reasoning results.
    
    Args:
        onto: The ontology object
        pre_stats: Dict with pre-reasoning statistics
        post_stats: Dict with post-reasoning statistics
        inconsistent_classes: List of inconsistent classes
        inferred_hierarchy: Dict of inferred class relationships
        inferred_properties: Dict of inferred property characteristics
        inferred_individuals: Dict of inferred individual relationships
    
    Returns:
        tuple: (report_str, has_issues)
    """
    report_lines = []
    has_issues = False
    
    def add_section(title):
        report_lines.extend([
            "\n" + "="*80,
            f"{title}",
            "="*80
        ])
    
    # 1. Executive Summary
    add_section("REASONING REPORT EXECUTIVE SUMMARY")
    
    # Ontology Consistency Status
    if inconsistent_classes:
        has_issues = True
        report_lines.append("❌ ONTOLOGY STATUS: Inconsistent")
        report_lines.append(f"   Found {len(inconsistent_classes)} inconsistent classes")
    else:
        report_lines.append("✅ ONTOLOGY STATUS: Consistent")
    
    # Changes Overview
    class_diff = post_stats['classes'] - pre_stats['classes']
    prop_diff = (post_stats['object_properties'] - pre_stats['object_properties'] +
                post_stats['data_properties'] - pre_stats['data_properties'])
    ind_diff = post_stats['individuals'] - pre_stats['individuals']
    
    report_lines.extend([
        f"\nStructural Changes:",
        f"  • Classes: {class_diff:+d}",
        f"  • Properties: {prop_diff:+d}",
        f"  • Individuals: {ind_diff:+d}"
    ])
    
    # 2. Detailed Statistics
    add_section("DETAILED STATISTICS")
    report_lines.extend([
        "\nPre-Reasoning:",
        f"  • Classes: {pre_stats['classes']}",
        f"  • Object Properties: {pre_stats['object_properties']}",
        f"  • Data Properties: {pre_stats['data_properties']}",
        f"  • Individuals: {pre_stats['individuals']}",
        "\nPost-Reasoning:",
        f"  • Classes: {post_stats['classes']}",
        f"  • Object Properties: {post_stats['object_properties']}",
        f"  • Data Properties: {post_stats['data_properties']}",
        f"  • Individuals: {post_stats['individuals']}"
    ])
    
    # 3. Consistency Issues
    if inconsistent_classes:
        add_section("CONSISTENCY ISSUES")
        report_lines.append("\nInconsistent Classes:")
        for cls in inconsistent_classes:
            report_lines.append(f"  • {cls.name}")
            has_issues = True
    
    # 4. Inferred Knowledge
    add_section("INFERRED KNOWLEDGE")
    
    # Class Hierarchy
    if inferred_hierarchy:
        report_lines.append("\nClass Hierarchy Changes:")
        for parent, data in inferred_hierarchy.items():
            if data.get('subclasses'):
                report_lines.append(f"\n  {parent}:")
                for sub in data['subclasses']:
                    report_lines.append(f"    ↳ {sub}")
            if data.get('equivalent'):
                report_lines.append(f"    ≡ Equivalent to: {', '.join(data['equivalent'])}")
    else:
        report_lines.append("\nNo new class hierarchy relationships inferred.")
    
    # Property Characteristics
    if inferred_properties:
        report_lines.append("\nInferred Property Characteristics:")
        for prop, chars in inferred_properties.items():
            report_lines.append(f"\n  {prop}:")
            for char in chars:
                report_lines.append(f"    • {char}")
    else:
        report_lines.append("\nNo new property characteristics inferred.")
    
    # Individual Classifications
    if inferred_individuals:
        report_lines.append("\nIndividual Inferences:")
        for ind, data in inferred_individuals.items():
            report_lines.append(f"\n  {ind}:")
            if data.get('types'):
                report_lines.append("    Types:")
                for t in data['types']:
                    report_lines.append(f"      • {t}")
            if data.get('properties'):
                report_lines.append("    Properties:")
                for p, vals in data['properties'].items():
                    report_lines.append(f"      • {p}: {', '.join(map(str, vals))}")
    else:
        report_lines.append("\nNo new individual classifications inferred.")
    
    # 5. Recommendations
    add_section("RECOMMENDATIONS")
    recommendations = []
    
    if inconsistent_classes:
        recommendations.append("❗ HIGH PRIORITY: Resolve inconsistencies in classes listed above.")
    
    if class_diff == 0 and prop_diff == 0 and ind_diff == 0:
        recommendations.append("⚠️ No structural changes after reasoning - verify if this is expected.")
    
    if not inferred_hierarchy and not inferred_properties and not inferred_individuals:
        recommendations.append("⚠️ No inferences made - consider enriching ontology axioms.")
        has_issues = True
    
    if recommendations:
        report_lines.extend(["\n" + rec for rec in recommendations])
    else:
        report_lines.append("\nNo critical issues found. Ontology appears to be well-structured.")
    
    return "\n".join(report_lines), has_issues

def main_ontology_generation(spec_file_path, data_file_path, output_owl_path, ontology_iri=DEFAULT_ONTOLOGY_IRI, save_format="rdfxml", use_reasoner=False, world_db_path=None):
    """
    Main function to generate the ontology.

    Args:
        spec_file_path (str): Path to the ontology specification CSV file.
        data_file_path (str): Path to the operational data CSV file.
        output_owl_path (str): Path to save the generated OWL file.
        ontology_iri (str): Base IRI for the new ontology.
        save_format (str): Format to save ontology ('rdfxml', 'ntriples', etc.)
        use_reasoner (bool): Whether to run the reasoner after population.
        world_db_path (str): Optional path to use a persistent World DB (e.g., 'ontology.sqlite3').
    """
    start_time = timing.time()
    main_logger.info("--- Starting Ontology Generation ---")
    main_logger.info(f"Specification file: {spec_file_path}")
    main_logger.info(f"Data file: {data_file_path}")
    main_logger.info(f"Output OWL file: {output_owl_path}")
    main_logger.info(f"Ontology IRI: {ontology_iri}")
    main_logger.info(f"Save format: {save_format}")
    main_logger.info(f"Run reasoner: {use_reasoner}")
    if world_db_path:
         main_logger.info(f"Using persistent world DB: {world_db_path}")

    try:
        # 1. Parse Specification
        specification = parse_specification(spec_file_path)
        if not specification:
            main_logger.error("Specification parsing failed or resulted in empty spec. Aborting.")
            return False # Indicate failure

        # 2. Create Ontology World and Ontology Object
        if world_db_path:
            # Use a persistent world (SQLite backend)
            main_logger.info(f"Initializing persistent World at: {world_db_path}")
            world = World(filename=world_db_path)
            onto = world.get_ontology(ontology_iri).load() # Load if exists, create otherwise
            main_logger.info(f"Ontology object obtained from persistent world: {onto}")
        else:
            # Use default in-memory world
             main_logger.info("Initializing in-memory World.")
             # It's safer to create a new world for each run unless merging is intended
             world = World() # Create a fresh world
             # world = default_world # Using default_world can have side effects between runs
             onto = world.get_ontology(ontology_iri)
             main_logger.info(f"Ontology object created in memory: {onto}")

        # 3. Define Ontology Structure (TBox)
        # Pass the 'onto' object created above
        defined_classes, defined_properties = define_ontology_structure(onto, specification)
        if not defined_classes: # Check if class definition was minimally successful
             main_logger.warning("Ontology structure definition resulted in no classes. Population might be empty.")
             # Continue for now, but population will likely fail checks

        # 4. Read Operational Data
        data_rows = read_data(data_file_path)
        
        # Track population success status
        population_successful = True
        failed_rows_count = 0
        
        if not data_rows:
             main_logger.warning("No data rows read from data file. Ontology will be populated with structure only.")
             # Population is technically successful if there's no data to populate
        else:
             # 5. Populate Ontology (ABox)
             try:
                 # Get number of failed rows from populate_ontology_from_data
                 failed_rows_count = populate_ontology_from_data(onto, data_rows, defined_classes, defined_properties)
                 if failed_rows_count == len(data_rows) and len(data_rows) > 0:
                      main_logger.error(f"Population failed for all {len(data_rows)} data rows.")
                      population_successful = False
                 elif failed_rows_count > 0:
                      main_logger.warning(f"Population completed with {failed_rows_count} of {len(data_rows)} failed rows.")
             except Exception as pop_exc:
                  main_logger.error(f"Critical error during population: {pop_exc}", exc_info=True)
                  population_successful = False

        # 6. Apply Reasoning (Optional)
        reasoning_successful = True
        if use_reasoner:
            main_logger.info("Applying reasoner (ensure HermiT or Pellet is configured)...")
            try:
                # Use with onto context for reasoning as well
                with onto:
                    # Collect pre-reasoning statistics
                    pre_stats = {
                        'classes': len(list(onto.classes())),
                        'object_properties': len(list(onto.object_properties())),
                        'data_properties': len(list(onto.data_properties())),
                        'individuals': len(list(onto.individuals()))
                    }
                    
                    # Log basic pre-reasoning info
                    main_logger.info("Starting reasoning process...")
                    sync_reasoner(infer_property_values=True, debug=2)
                    
                    # Collect reasoning results
                    inconsistent = list(default_world.inconsistent_classes())
                    
                    # Collect inferred hierarchy
                    inferred_hierarchy = {}
                    for cls in onto.classes():
                        inferred = {
                            'subclasses': [sub.name for sub in cls.subclasses() 
                                         if not any(sub in c.subclasses() for c in cls.is_a)],
                            'equivalent': [eq.name for eq in cls.equivalent_to if eq != cls]
                        }
                        if inferred['subclasses'] or inferred['equivalent']:
                            inferred_hierarchy[cls.name] = inferred
                    
                    # Collect property inferences
                    inferred_properties = {}
                    for prop in onto.properties():
                        characteristics = []
                        if prop.is_functional_for is not None:
                            characteristics.append("Functional")
                        if getattr(prop, 'is_transitive_for', None) is not None:
                            characteristics.append("Transitive")
                        if getattr(prop, 'is_symmetric_for', None) is not None:
                            characteristics.append("Symmetric")
                        if characteristics:
                            inferred_properties[prop.name] = characteristics
                    
                    # Collect individual inferences
                    inferred_individuals = {}
                    for ind in onto.individuals():
                        inferred = {
                            'types': [cls.name for cls in ind.is_a 
                                    if cls not in ind.INDIRECT_is_instance_of],
                            'properties': {}
                        }
                        for prop in onto.properties():
                            try:
                                values = list(prop[ind])
                                if values:
                                    inferred['properties'][prop.name] = [
                                        getattr(v, 'name', str(v)) for v in values
                                    ]
                            except Exception:
                                continue
                        if inferred['types'] or inferred['properties']:
                            inferred_individuals[ind.name] = inferred
                    
                    # Collect post-reasoning statistics
                    post_stats = {
                        'classes': len(list(onto.classes())),
                        'object_properties': len(list(onto.object_properties())),
                        'data_properties': len(list(onto.data_properties())),
                        'individuals': len(list(onto.individuals()))
                    }
                    
                    # Generate and log the report
                    report, has_issues = generate_reasoning_report(
                        onto, pre_stats, post_stats, inconsistent,
                        inferred_hierarchy, inferred_properties, inferred_individuals
                    )
                    
                    # Log the report
                    main_logger.info("\nReasoning Report:\n" + report)
                    
                    # Update reasoning_successful based on issues
                    if has_issues:
                        main_logger.warning("Reasoning completed but potential issues were identified.")
                    else:
                        main_logger.info("Reasoning completed successfully with no issues identified.")
                
            except OwlReadyInconsistentOntologyError:
                main_logger.error("REASONING FAILED: Ontology is inconsistent!")
                reasoning_successful = False
                # Optionally check inconsistent classes:
                try:
                     inconsistent = list(default_world.inconsistent_classes()) # Or use world variable if persistent
                     main_logger.error(f"Inconsistent classes detected by reasoner: {inconsistent}")
                except Exception as e_inc:
                     main_logger.error(f"Could not retrieve inconsistent classes: {e_inc}")
                # Consider not saving an inconsistent ontology or saving to a different file
                # return False # Indicate failure
            except NameError as ne:
                 if "sync_reasoner" in str(ne):
                     main_logger.error("Reasoning failed: Reasoner (e.g., HermiT) might not be installed or found by owlready2.")
                 else:
                      main_logger.error(f"Unexpected NameError during reasoning: {ne}")
                 reasoning_successful = False
            except Exception as e:
                main_logger.error(f"An error occurred during reasoning: {e}", exc_info=True)
                reasoning_successful = False

        # 7. Save Ontology
        main_logger.info(f"Saving ontology to {output_owl_path} in '{save_format}' format...")
        onto.save(file=output_owl_path, format=save_format)
        main_logger.info("Ontology saved successfully.")

        if world_db_path:
            # Explicitly close the world database connection
            try:
                world.close()
                main_logger.info(f"Persistent world DB {world_db_path} closed.")
            except Exception as e_close:
                main_logger.warning(f"Could not explicitly close world DB: {e_close}")

        # Return success status based on all steps
        # For this case, we'll prioritize population success over reasoning
        # You can adjust this logic based on your requirements
        return population_successful and (not use_reasoner or reasoning_successful)

    except Exception as e:
        main_logger.exception("A critical error occurred during ontology generation.")
        # No sys.exit here, return False to indicate failure to the caller
        return False

    finally:
        end_time = timing.time()
        main_logger.info(f"--- Ontology Generation Finished ---")
        main_logger.info(f"Total time: {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an OWL ontology from specification and data CSV files.")
    parser.add_argument("spec_file", help="Path to the ontology specification CSV file (e.g., opera_spec.csv).")
    parser.add_argument("data_file", help="Path to the operational data CSV file (e.g., sample_data.csv).")
    parser.add_argument("output_file", help="Path to save the generated OWL ontology file (e.g., manufacturing.owl).")
    parser.add_argument("--iri", default=DEFAULT_ONTOLOGY_IRI, help=f"Base IRI for the ontology (default: {DEFAULT_ONTOLOGY_IRI}).")
    parser.add_argument("--format", default="rdfxml", choices=["rdfxml", "ntriples", "nquads"], help="Format for saving the ontology (default: rdfxml).")
    parser.add_argument("--reasoner", action="store_true", help="Run the reasoner (e.g., HermiT) after population.")
    parser.add_argument("--worlddb", default=None, help="Path to use/create a persistent SQLite world database (e.g., my_ontology.sqlite3).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging for all modules.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress INFO level logging, only show warnings and errors.")

    args = parser.parse_args()

    # Setup Logging Level based on arguments
    log_level = logging.INFO
    if args.verbose:
        log_level = logging.DEBUG
    elif args.quiet:
        log_level = logging.WARNING

    # Configure logging BEFORE any logging calls in modules
    logging.basicConfig(level=log_level, format=LOG_FORMAT, stream=sys.stdout) # Log to stdout

    # Set level for all loggers obtained via getLogger
    # This ensures modules imported earlier also adhere to the command line level
    logging.getLogger().setLevel(log_level)
    for handler in logging.getLogger().handlers:
            handler.setLevel(log_level)

    main_logger.info("Logging configured.")
    if args.verbose:
         main_logger.info("Verbose logging enabled.")

    # Execute main function
    success = main_ontology_generation(
        args.spec_file,
        args.data_file,
        args.output_file,
        args.iri,
        args.format,
        args.reasoner,
        args.worlddb
    )

    # Exit with appropriate code
    if success:
        main_logger.info("Ontology generation process completed successfully.")
        sys.exit(0)
    else:
        main_logger.error("Ontology generation process failed.")
        sys.exit(1)