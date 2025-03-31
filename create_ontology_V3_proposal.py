# -*- coding: utf-8 -*-
# Combined and Updated Ontology Generation Code (v4 - Fixes & Enhancements)

import csv
import logging
import sys
import time as timing
import argparse
import re
import os
from owlready2 import *
from datetime import datetime, date, time # time might not be needed if not used in spec
from typing import List, Dict, Optional, Set, Tuple, Any # For type hinting

# --- Configuration ---
DEFAULT_ONTOLOGY_IRI = "http://example.com/manufacturing_ontology.owl"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
SPEC_PARENT_CLASS_COLUMN = 'Parent Class' # Assumed column name for hierarchy

# --- Language Mapping for Alternative Reason Descriptions ---
# Mapping from country descriptions to BCP 47 language tags
COUNTRY_TO_LANGUAGE: Dict[str, str] = {
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
# Defines a default linear sequence for common equipment types
DEFAULT_EQUIPMENT_SEQUENCE: Dict[str, int] = {
    "Filler": 1,
    "Cartoner": 2,
    "Bundler": 3,
    "CaseFormer": 4, # Assuming these exist based on common patterns
    "CasePacker": 5,
    "CaseSealer": 6, # Assuming these exist based on common patterns
    "Palletizer": 7,
    # Add any other classes with default positions if needed
}

# --- Logging Setup ---
# Basic config will be set in the main block
logger = logging.getLogger(__name__) # Logger for definition module
pop_logger = logging.getLogger("ontology_population") # Logger for population module
main_logger = logging.getLogger("create_ontology") # Logger for main script

#======================================================================#
#                 ontology_definition.py Module Code                 #
#======================================================================#

# Mapping from XSD types in the spec to Python types/owlready2 constructs
XSD_TYPE_MAP: Dict[str, type] = {
    "xsd:string": str,
    "xsd:decimal": float,  # Using float for compatibility with owlready2. High precision Decimal is possible but adds complexity.
    "xsd:integer": int,
    "xsd:dateTime": datetime,
    "xsd:date": date,
    "xsd:time": time,
    "xsd:boolean": bool,
    "xsd:anyURI": str,
    "xsd:string (with lang tag)": locstr, # owlready2 localized string
}

def parse_specification(spec_file_path: str) -> List[Dict[str, str]]:
    """Parses the ontology specification CSV file."""
    logger.info(f"Parsing specification file: {spec_file_path}")
    spec_list: List[Dict[str, str]] = []
    try:
        with open(spec_file_path, mode='r', encoding='utf-8-sig') as infile: # Use utf-8-sig to handle potential BOM
            reader = csv.DictReader(infile)
            # Basic check for expected columns (optional but recommended)
            # expected_cols = {'Proposed OWL Entity', 'Proposed OWL Property', 'Parent Class', ...}
            # if not expected_cols.issubset(reader.fieldnames):
            #     logger.warning(f"Specification file might be missing expected columns. Found: {reader.fieldnames}")
            spec_list = list(reader)
            logger.info(f"Successfully parsed {len(spec_list)} rows from specification.")
            return spec_list
    except FileNotFoundError:
        logger.error(f"Specification file not found: {spec_file_path}")
        raise
    except Exception as e:
        logger.error(f"Error parsing specification file {spec_file_path}: {e}")
        raise
    return [] # Return empty list on error if not raising

def define_ontology_structure(onto: Ontology, specification: List[Dict[str, str]]) -> Tuple[Dict[str, ThingClass], Dict[str, PropertyClass], Dict[str, bool]]:
    """
    Defines OWL classes and properties based on the parsed specification.

    Returns:
        tuple: (defined_classes, defined_properties, property_is_functional)
            - defined_classes: Dict mapping class name to owlready2 class object.
            - defined_properties: Dict mapping property name to owlready2 property object.
            - property_is_functional: Dict mapping property name to boolean indicating functionality.
    """
    logger.info(f"Defining ontology structure in: {onto.base_iri}")
    defined_classes: Dict[str, ThingClass] = {}
    defined_properties: Dict[str, PropertyClass] = {}
    property_is_functional: Dict[str, bool] = {}  # Track which properties are functional based on spec
    class_metadata: Dict[str, Dict[str, Any]] = {} # Store metadata like notes per class

    # --- Pre-process Spec for Class Metadata and Hierarchy ---
    logger.debug("--- Pre-processing specification for class details ---")
    all_class_names: Set[str] = set()
    class_parents: Dict[str, str] = {} # {child_name: parent_name}
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
        if "Thing" not in all_class_names and "owl:Thing" not in all_class_names:
             pass # Thing is implicitly available via owlready2

        defined_order: List[str] = [] # Track definition order for hierarchy
        definition_attempts = 0
        max_attempts = len(all_class_names) + 5 # Allow some leeway for complex hierarchies

        classes_to_define: Set[str] = set(cn for cn in all_class_names if cn.lower() != "owl:thing") # Exclude Thing variants

        while classes_to_define and definition_attempts < max_attempts:
            defined_in_pass: Set[str] = set()
            for class_name in sorted(list(classes_to_define)): # Sort for somewhat deterministic order
                 parent_name = class_parents.get(class_name)
                 parent_class_obj: ThingClass = Thing # Default parent is Thing

                 if parent_name:
                     if parent_name == "Thing" or parent_name.lower() == "owl:thing": # Handle case variation
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
                         # Ensure class name is valid Python identifier if needed by backend
                         safe_class_name = re.sub(r'\W|^(?=\d)', '_', class_name)
                         if safe_class_name != class_name:
                             logger.warning(f"Class name '{class_name}' sanitized to '{safe_class_name}' for internal use. Using original name for IRI.")
                             # Sticking with original name as owlready2 often handles non-standard chars in IRIs
                         new_class: ThingClass = types.new_class(class_name, (parent_class_obj,))
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

                 except Exception as e:
                     logger.error(f"Error defining class '{class_name}' with parent '{getattr(parent_class_obj,'name','N/A')}': {e}")
                     # Let it retry, might be a transient issue or solvable in later pass

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
    temp_inverse_map: Dict[str, str] = {} # Stores {prop_name: inverse_name}

    with onto:
        # Define properties first without inverse, handle inverse in a second pass
        for row in properties_to_process:
            prop_name = row.get('Proposed OWL Property','').strip()
            if not prop_name or prop_name in defined_properties:
                continue # Skip empty or already defined properties

            prop_type_str = row.get('OWL Property Type', '').strip()
            domain_str = row.get('Domain', '').strip()
            range_str = row.get('Target/Range (xsd:) / Target Class', '').strip()
            characteristics_str = row.get('OWL Property Characteristics', '').strip().lower() # Normalize
            inverse_prop_name = row.get('Inverse Property', '').strip()

            if not prop_type_str or not domain_str or not range_str:
                logger.warning(f"Skipping property '{prop_name}' due to missing type, domain, or range in spec.")
                continue

            # Determine parent classes for the property
            parent_classes: List[type] = []
            base_prop_type: Optional[type] = None
            if prop_type_str == 'ObjectProperty':
                base_prop_type = ObjectProperty
            elif prop_type_str == 'DatatypeProperty':
                base_prop_type = DataProperty
            else:
                logger.warning(f"Unknown property type '{prop_type_str}' for property '{prop_name}'. Skipping.")
                continue

            parent_classes.append(base_prop_type)

            # Add characteristics
            is_functional = 'functional' in characteristics_str
            property_is_functional[prop_name] = is_functional # Track functionality status
            if is_functional: parent_classes.append(FunctionalProperty)
            if 'inversefunctional' in characteristics_str: parent_classes.append(InverseFunctionalProperty)
            if 'transitive' in characteristics_str: parent_classes.append(TransitiveProperty)
            if 'symmetric' in characteristics_str: parent_classes.append(SymmetricProperty)
            if 'asymmetric' in characteristics_str: parent_classes.append(AsymmetricProperty)
            if 'reflexive' in characteristics_str: parent_classes.append(ReflexiveProperty)
            if 'irreflexive' in characteristics_str: parent_classes.append(IrreflexiveProperty)

            try:
                # Define the property
                new_prop: PropertyClass = types.new_class(prop_name, tuple(parent_classes))

                # Set Domain
                domain_class_names = [dc.strip() for dc in domain_str.split('|')]
                prop_domain: List[ThingClass] = []
                valid_domain_found = False
                for dc_name in domain_class_names:
                    domain_class = defined_classes.get(dc_name)
                    if domain_class:
                        prop_domain.append(domain_class)
                        valid_domain_found = True
                    elif dc_name == "Thing" or dc_name.lower() == "owl:thing": # Allow Thing as domain
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
                    prop_range: List[ThingClass] = []
                    valid_range_found = False
                    for rc_name in range_class_names:
                        range_class = defined_classes.get(rc_name)
                        if range_class:
                            prop_range.append(range_class)
                            valid_range_found = True
                        elif rc_name == "Thing" or rc_name.lower() == "owl:thing": # Allow Thing as range
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
                logger.debug(f"Defined Property: {new_prop.iri} of type {prop_type_str} with characteristics {' '.join([p.__name__ for p in parent_classes[1:]]) if len(parent_classes) > 1 else 'None'}")

                # Store inverse relationship for later processing
                if inverse_prop_name and base_prop_type is ObjectProperty:
                    temp_inverse_map[prop_name] = inverse_prop_name

            except Exception as e:
                logger.error(f"Error defining property '{prop_name}': {e}")

    # --- Pass 3: Set Inverse Properties ---
    logger.debug("--- Setting Inverse Properties ---")
    with onto: # Ensure changes are applied within the ontology context
        for prop_name, inverse_name in temp_inverse_map.items():
            prop = defined_properties.get(prop_name)
            inverse_prop = defined_properties.get(inverse_name)

            if prop and inverse_prop:
                try:
                    # Check if already set to the desired value to avoid unnecessary writes/warnings if possible
                    current_inverse = getattr(prop, "inverse_property", None)
                    if current_inverse != inverse_prop:
                        prop.inverse_property = inverse_prop
                        logger.debug(f"Set inverse_property for {prop.name} to {inverse_prop.name}")
                    # Also explicitly set the inverse's inverse property back
                    current_inverse_of_inverse = getattr(inverse_prop, "inverse_property", None)
                    if current_inverse_of_inverse != prop:
                         inverse_prop.inverse_property = prop
                         logger.debug(f"Set inverse_property for {inverse_prop.name} back to {prop.name}")
                except Exception as e:
                    logger.error(f"Error setting inverse property between '{prop_name}' and '{inverse_name}': {e}")
            elif not prop:
                logger.warning(f"Property '{prop_name}' not found while trying to set inverse '{inverse_name}'.")
            elif not inverse_prop:
                logger.warning(f"Inverse property '{inverse_name}' not found for property '{prop_name}'.")


    # --- Pass 4: Define Property Restrictions (Optional) ---
    # Implementation can be added here if needed, iterating spec again.
    logger.debug("--- Skipping complex property restrictions definition ---")

    logger.info("Ontology structure definition complete.")
    return defined_classes, defined_properties, property_is_functional

#======================================================================#
#               ontology_population.py Module Code                   #
#======================================================================#

# --- Helper Functions ---

def parse_equipment_class(equipment_name: Optional[str]) -> Optional[str]:
    """
    Parses the EquipmentClass from the EQUIPMENT_NAME.
    Rule: Extracts the part after the last underscore. Returns None if input is invalid.
    Example: FIPCO009_Filler -> Filler
    """
    if not equipment_name or not isinstance(equipment_name, str):
        return None
    if '_' in equipment_name:
        parts = equipment_name.split('_')
        class_part = parts[-1]
        # Basic sanity check - is the class part reasonable? (e.g., not just digits)
        if class_part and not class_part.isdigit():
             pop_logger.debug(f"Parsed equipment class '{class_part}' from '{equipment_name}'")
             return class_part
        else:
             pop_logger.warning(f"Parsed part '{class_part}' from '{equipment_name}' seems invalid (e.g., digits only). Treating whole name as class.")
             return equipment_name # Fallback
    pop_logger.debug(f"No underscore found in EQUIPMENT_NAME '{equipment_name}', using whole name as class.")
    return equipment_name # Fallback if no underscore

def safe_cast(value: Any, target_type: type, default: Any = None) -> Any:
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
            # Handles standard float conversion
            return float(value_str)
        # Note: xsd:decimal maps to float based on XSD_TYPE_MAP
        if target_type is bool:
            val_lower = value_str.lower()
            if val_lower in ['true', '1', 't', 'y', 'yes']:
                return True
            elif val_lower in ['false', '0', 'f', 'n', 'no']:
                return False
            else:
                pop_logger.warning(f"Could not interpret {original_value_repr} as boolean.")
                return None
        if target_type is datetime:
            # Try parsing common formats. owlready2 stores datetime naive.
            # Parsing tz info helps ensure correctness if data has mixed offsets,
            # but the final stored value will be naive.
            fmts = [
                "%Y-%m-%d %H:%M:%S.%f %z", "%Y-%m-%d %H:%M:%S %z",
                "%Y-%m-%d %H:%M:%S.%f",   "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f%z","%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f",  "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d",
            ]
            parsed_dt = None
            clean_value = value_str.replace('Z', '+0000')
            clean_value = re.sub(r'([+-])(\d{2})\s(\d{2})$', r'\1\2\3', clean_value)
            # Handle potential missing microseconds before timezone (common issue)
            clean_value = re.sub(r'(\d{2}:\d{2}:\d{2})\s([+-]\d{4})', r'\1.000 \2', clean_value)

            for fmt in fmts:
                try:
                    parsed_dt = datetime.strptime(clean_value, fmt)
                    if parsed_dt.tzinfo:
                        pop_logger.debug(f"Parsed datetime {original_value_repr} with timezone {parsed_dt.tzinfo}, storing as naive datetime.")
                        # Convert to UTC and make naive, or just make naive directly.
                        # Making naive directly loses original offset info but is simplest for owlready2.
                        parsed_dt = parsed_dt.replace(tzinfo=None)
                    #pop_logger.debug(f"Successfully parsed datetime {original_value_repr} using format '{fmt}' -> {parsed_dt}")
                    return parsed_dt
                except ValueError:
                    continue # Try next format
            if parsed_dt is None:
                pop_logger.warning(f"Could not parse datetime string {original_value_repr} with known formats.")
                return default

        if target_type is date:
             try:
                 return date.fromisoformat(value_str) # Assumes YYYY-MM-DD
             except ValueError:
                 pop_logger.warning(f"Could not parse date string {original_value_repr} as ISO date.")
                 return default
        if target_type is time:
             try:
                 return time.fromisoformat(value_str) # Assumes HH:MM:SS[.ffffff][+/-HH:MM]
             except ValueError:
                 pop_logger.warning(f"Could not parse time string {original_value_repr} as ISO time.")
                 return default

        # General cast attempt for types not explicitly handled above (e.g., locstr handled by owlready2)
        if target_type is locstr: # Let owlready2 handle locstr creation later
            return value_str

        return target_type(value_str) # Fallback attempt

    except (ValueError, TypeError, InvalidOperation) as e:
        pop_logger.warning(f"Failed to cast {original_value_repr} to {target_type.__name__}: {e}. Returning default: {default}")
        return default
    except Exception as e:
        pop_logger.error(f"Unexpected error casting {original_value_repr} to {target_type.__name__}: {e}", exc_info=False)
        return default


def get_or_create_individual(onto_class: ThingClass, individual_name_base: Any, onto: Ontology, add_labels: Optional[List[str]] = None) -> Optional[Thing]:
    """
    Gets an individual if it exists, otherwise creates it.
    Uses a class-prefixed, sanitized name for the individual IRI. Returns None on failure.
    """
    if not individual_name_base:
        pop_logger.warning(f"Cannot get/create individual with empty base name for class {onto_class.name if onto_class else 'None'}")
        return None
    if not onto_class:
        pop_logger.error(f"Cannot get/create individual: onto_class parameter is None for base name '{individual_name_base}'.")
        return None

    # 1. Sanitize the base name
    safe_base = re.sub(r'\s+', '_', str(individual_name_base).strip())
    safe_base = re.sub(r'[^\w\-.]', '', safe_base) # Keep word chars, hyphen, period
    if not safe_base: # Handle cases where name becomes empty
        fallback_hash = abs(hash(str(individual_name_base)))
        safe_base = f"UnnamedData_{fallback_hash}"
        pop_logger.warning(f"Sanitized name for '{individual_name_base}' became empty. Using fallback: {safe_base}")

    # 2. Create the class-specific, sanitized name
    final_name = f"{onto_class.name}_{safe_base}"

    # 3. Check if individual exists
    individual = onto[final_name]

    if individual:
        # Check if the existing individual is of the correct type
        if isinstance(individual, onto_class):
            # Optionally add labels even if retrieved
            if add_labels:
                current_labels = individual.label
                for lbl in add_labels:
                    if lbl and isinstance(lbl, str) and lbl not in current_labels:
                         individual.label.append(lbl)
            return individual
        else:
            pop_logger.error(f"IRI collision: Individual '{final_name}' ({individual.iri}) exists but is not of expected type {onto_class.name}. It has type(s): {individual.is_a}. Cannot proceed reliably.")
            raise TypeError(f"IRI collision: {final_name} exists with wrong type.")

    # 4. Create the new individual
    try:
        pop_logger.debug(f"Creating new individual '{final_name}' of class {onto_class.name}")
        new_individual = onto_class(final_name, namespace=onto)

        # Add labels if provided
        if add_labels:
            for lbl in add_labels:
                if lbl and isinstance(lbl, str): new_individual.label.append(lbl)

        return new_individual
    except Exception as e:
        pop_logger.error(f"Failed to create individual '{final_name}' of class {onto_class.name}: {e}")
        return None


# --- Main Population Function ---

def populate_ontology_from_data(onto: Ontology,
                                data_rows: List[Dict[str, Any]],
                                defined_classes: Dict[str, ThingClass],
                                defined_properties: Dict[str, PropertyClass],
                                property_is_functional: Dict[str, bool]
                               ) -> Tuple[int, Dict[str, Thing], Dict[str, int]]:
    """
    Populates the ontology with individuals and relations from data rows.

    Returns:
        tuple: (failed_rows_count, created_equipment_class_inds, equipment_class_positions)
            - failed_rows_count: Number of rows that failed processing.
            - created_equipment_class_inds: Maps equipment class name (str) to its individual object.
            - equipment_class_positions: Maps equipment class name (str) to its default sequence position (int).
    """
    pop_logger.info(f"Starting ontology population with {len(data_rows)} data rows.")

    # Track equipment class sequence positions and created individuals
    equipment_class_positions: Dict[str, int] = {}
    created_equipment_class_inds: Dict[str, Thing] = {} # {eq_class_name_str: eq_class_ind_obj}

    # --- Get Class Objects ---
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
        return len(data_rows), {}, {} # Return all rows as failed, empty dicts

    # --- Get Property Objects ---
    prop_map: Dict[str, Optional[PropertyClass]] = {}
    # List all properties potentially used in population or later sequence setup
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
        # Relationships (Object Props - Use specific names from spec!)
        "memberOfClass", "locatedInPlant", "partOfArea", "locatedInProcessCell",
        "isPartOfProductionLine", "involvesResource", "associatedWithProductionRequest",
        "usesMaterial", "occursDuring", "duringShift", "eventHasState", "eventHasReason",
        "classIsUpstreamOf", # Specific name
        "classIsDownstreamOf", # Specific name
        "equipmentIsUpstreamOf", # Specific name
        "equipmentIsDownstreamOf" # Specific name
    ]

    # Define props critical for linking or subsequent steps like sequencing
    essential_prop_names: Set[str] = {
        "equipmentId", "lineId", "involvesResource", "occursDuring", "startTime",
        # Properties needed for Equipment -> EquipmentClass linking and sequence setup
        "memberOfClass", "equipmentClassId", "isPartOfProductionLine",
        "defaultSequencePosition",
        # Properties needed for setting up sequence relationships later
        "classIsUpstreamOf", "equipmentIsUpstreamOf"
    }

    missing_essential_props = []
    for name in prop_names:
        prop_map[name] = defined_properties.get(name)
        if not prop_map[name] and name in essential_prop_names:
             missing_essential_props.append(name)
        elif not prop_map[name]:
             # Only warn if property was expected to be defined (i.e., in the original spec list)
             if any(row.get('Proposed OWL Property') == name for row in specification):
                pop_logger.warning(f"Property '{name}' (from spec) not found in defined_properties map. Population using this property will be skipped.")
             # else: don't warn for properties we added programmatically but might not be in spec

    if missing_essential_props:
        pop_logger.error(f"Cannot reliably proceed with population. Missing essential properties definitions: {missing_essential_props}")
        return len(data_rows), {}, {} # Return all rows as failed, empty dicts


    # --- Process Data Rows ---
    with onto: # Use the ontology context for creating individuals
        successful_rows = 0
        failed_rows = 0
        for i, row in enumerate(data_rows):
            row_num = i + 2 # 1-based index + header row = line number in CSV
            pop_logger.debug(f"--- Processing Row {row_num} ---")
            try:
                # --- Create / Retrieve Core Asset Hierarchy Individuals ---
                plant_id = safe_cast(row.get('PLANT'), str)
                if not plant_id:
                    pop_logger.error(f"Row {row_num}: Missing PLANT ID. Skipping row.")
                    failed_rows += 1
                    continue
                plant_labels = [plant_id]
                plant_ind = get_or_create_individual(cls_Plant, plant_id, onto, add_labels=plant_labels)
                prop_plantId = prop_map.get("plantId")
                if plant_ind and prop_plantId:
                    # Functional Property: Use getattr/setattr
                    if plant_id is not None and getattr(plant_ind, "plantId", None) != plant_id:
                        setattr(plant_ind, "plantId", plant_id)

                area_id = safe_cast(row.get('GH_FOCUSFACTORY'), str) # Using FocusFactory as Area ID based on spec assumption
                if not area_id: area_id = "UnknownArea" # Fallback if missing
                area_unique_base = f"{plant_id}_{area_id}"
                area_labels = [area_id]
                area_ind = get_or_create_individual(cls_Area, area_unique_base, onto, add_labels=area_labels)
                if area_ind:
                    prop_areaId = prop_map.get("areaId")
                    if prop_areaId:
                         # Functional Property: Use getattr/setattr
                        if area_id is not None and getattr(area_ind, "areaId", None) != area_id:
                            setattr(area_ind, "areaId", area_id)

                    # Add relationship: Area locatedInPlant Plant (NON-FUNCTIONAL per spec)
                    prop_locatedInPlant = prop_map.get("locatedInPlant")
                    if prop_locatedInPlant and plant_ind:
                         # Non-Functional: Use append if not already present
                        if plant_ind not in area_ind.locatedInPlant:
                            area_ind.locatedInPlant.append(plant_ind)
                            pop_logger.debug(f"Linked {area_ind.name} locatedInPlant {plant_ind.name}")

                pcell_id = safe_cast(row.get('PHYSICAL_AREA'), str) # Using PhysicalArea as ProcessCell ID assumption
                if not pcell_id: pcell_id = "UnknownProcessCell" # Fallback
                pcell_unique_base = f"{area_unique_base}_{pcell_id}"
                pcell_labels = [pcell_id]
                pcell_ind = get_or_create_individual(cls_ProcessCell, pcell_unique_base, onto, add_labels=pcell_labels)
                if pcell_ind:
                    prop_processCellId = prop_map.get("processCellId")
                    if prop_processCellId:
                         # Functional Property: Use getattr/setattr
                        if pcell_id is not None and getattr(pcell_ind, "processCellId", None) != pcell_id:
                            setattr(pcell_ind, "processCellId", pcell_id)

                    # Add relationship: ProcessCell partOfArea Area (NON-FUNCTIONAL per spec)
                    prop_partOfArea = prop_map.get("partOfArea")
                    if prop_partOfArea and area_ind:
                        # Non-Functional: Use append if not already present
                        if area_ind not in pcell_ind.partOfArea:
                            pcell_ind.partOfArea.append(area_ind)
                            pop_logger.debug(f"Linked {pcell_ind.name} partOfArea {area_ind.name}")

                line_id = safe_cast(row.get('LINE_NAME'), str)
                if not line_id:
                    pop_logger.error(f"Row {row_num}: Missing LINE_NAME. Skipping row.")
                    failed_rows += 1
                    continue
                line_unique_base = f"{pcell_unique_base}_{line_id}"
                line_labels = [line_id]
                line_ind = get_or_create_individual(cls_ProductionLine, line_unique_base, onto, add_labels=line_labels)
                if line_ind:
                    prop_lineId = prop_map.get("lineId")
                    if prop_lineId:
                         # Functional Property: Use getattr/setattr
                        if line_id is not None and getattr(line_ind, "lineId", None) != line_id:
                            setattr(line_ind, "lineId", line_id)

                    # Add relationship: ProductionLine locatedInProcessCell ProcessCell (NON-FUNCTIONAL per spec)
                    prop_locatedInProcessCell = prop_map.get("locatedInProcessCell")
                    if prop_locatedInProcessCell and pcell_ind:
                        # Non-Functional: Use append if not already present
                        if pcell_ind not in line_ind.locatedInProcessCell:
                            line_ind.locatedInProcessCell.append(pcell_ind)
                            pop_logger.debug(f"Linked {line_ind.name} locatedInProcessCell {pcell_ind.name}")


                # --- Identify the Resource (Line or Equipment) for the Event ---
                eq_id_raw = row.get('EQUIPMENT_ID')
                eq_id_str = safe_cast(eq_id_raw, str) # Keep as string for ID/lookup
                eq_name = safe_cast(row.get('EQUIPMENT_NAME'), str)
                eq_type = safe_cast(row.get('EQUIPMENT_TYPE'), str) # 'Line' or 'Equipment'

                equipment_ind: Optional[Thing] = None
                resource_individual: Optional[Thing] = None # This will hold the individual linked by EventRecord
                resource_base_id: Optional[str] = None  # Base ID used for naming related individuals

                if eq_type == 'Line' and line_ind:
                    resource_individual = line_ind
                    resource_base_id = line_unique_base # Use the unique line base name
                    pop_logger.debug(f"Row {row_num}: Identified as Line record for: {line_id}")

                elif eq_type == 'Equipment' and eq_id_str and cls_Equipment:
                    pop_logger.debug(f"Row {row_num}: Identified as Equipment record for EQ_ID: {eq_id_str}, EQ_NAME: {eq_name}")
                    # Create Equipment individual
                    eq_unique_base = eq_id_str # Assume equipment ID is unique enough
                    eq_labels = [f"ID:{eq_id_str}"]
                    if eq_name: eq_labels.insert(0, eq_name)

                    equipment_ind = get_or_create_individual(cls_Equipment, eq_unique_base, onto, add_labels=eq_labels)
                    if equipment_ind:
                        resource_individual = equipment_ind
                        resource_base_id = f"Eq_{eq_unique_base}" # Prefix for clarity

                        # Set Equipment properties
                        prop_equipmentId = prop_map.get("equipmentId")
                        if prop_equipmentId:
                             # Functional Property: Use getattr/setattr
                            if eq_id_str is not None and getattr(equipment_ind, "equipmentId", None) != eq_id_str:
                                setattr(equipment_ind, "equipmentId", eq_id_str)

                        prop_equipmentName = prop_map.get("equipmentName")
                        if prop_equipmentName and eq_name:
                            # Non-functional - append if not present
                            if eq_name not in equipment_ind.equipmentName:
                                equipment_ind.equipmentName.append(eq_name)

                        prop_equipmentModel = prop_map.get("equipmentModel")
                        if prop_equipmentModel:
                            model = safe_cast(row.get('EQUIPMENT_MODEL'), str)
                            if model is not None and getattr(equipment_ind, "equipmentModel", None) != model:
                                setattr(equipment_ind, "equipmentModel", model)

                        prop_complexity = prop_map.get("complexity")
                        if prop_complexity:
                            complexity = safe_cast(row.get('COMPLEXITY'), str)
                            if complexity:
                                # Non-functional - append if not present
                                if complexity not in equipment_ind.complexity:
                                     equipment_ind.complexity.append(complexity)

                        prop_alternativeModel = prop_map.get("alternativeModel")
                        if prop_alternativeModel:
                            alt_model = safe_cast(row.get('MODEL'), str)
                            if alt_model:
                                # Non-functional - append if not present
                                if alt_model not in equipment_ind.alternativeModel:
                                     equipment_ind.alternativeModel.append(alt_model)

                        # Link Equipment to ProductionLine (NON-FUNCTIONAL per spec)
                        prop_isPartOfProductionLine = prop_map.get("isPartOfProductionLine")
                        if prop_isPartOfProductionLine and line_ind:
                            # Non-Functional: Use append if not already present
                            if line_ind not in equipment_ind.isPartOfProductionLine:
                                equipment_ind.isPartOfProductionLine.append(line_ind)
                                pop_logger.debug(f"Linked {equipment_ind.name} isPartOfProductionLine {line_ind.name}")

                        # Parse and link EquipmentClass
                        prop_memberOfClass = prop_map.get("memberOfClass")
                        prop_equipmentClassId = prop_map.get("equipmentClassId")
                        prop_defaultSequencePosition = prop_map.get("defaultSequencePosition")
                        if cls_EquipmentClass and prop_memberOfClass and prop_equipmentClassId and prop_defaultSequencePosition:
                            eq_class_name = parse_equipment_class(eq_name)
                            if eq_class_name:
                                pop_logger.debug(f"Attempting to get/create EquipmentClass: {eq_class_name}")
                                eq_class_labels = [eq_class_name]
                                eq_class_ind = get_or_create_individual(cls_EquipmentClass, eq_class_name, onto, add_labels=eq_class_labels)

                                if eq_class_ind:
                                    pop_logger.debug(f"Successfully got/created EquipmentClass individual: {eq_class_ind.name}")
                                    # Add to tracking dict if not already there
                                    if eq_class_name not in created_equipment_class_inds:
                                         created_equipment_class_inds[eq_class_name] = eq_class_ind

                                    # Assign equipmentClassId (FUNCTIONAL per spec)
                                    if eq_class_name is not None and getattr(eq_class_ind, "equipmentClassId", None) != eq_class_name:
                                         setattr(eq_class_ind, "equipmentClassId", eq_class_name)

                                    # Link Equipment to EquipmentClass (FUNCTIONAL per spec)
                                    if eq_class_ind is not None and getattr(equipment_ind, "memberOfClass", None) != eq_class_ind:
                                        setattr(equipment_ind, "memberOfClass", eq_class_ind)
                                        pop_logger.debug(f"Linking {equipment_ind.name} memberOfClass {eq_class_ind.name}")

                                    # Set default sequence position *on the class individual* (FUNCTIONAL per spec)
                                    default_pos = DEFAULT_EQUIPMENT_SEQUENCE.get(eq_class_name)
                                    if default_pos is not None:
                                        existing_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
                                        # Assign only if not already set or if forced update is desired
                                        if default_pos is not None and (existing_pos is None or existing_pos != default_pos):
                                            pop_logger.debug(f"Assigning default sequence position {default_pos} to class {eq_class_name} ({eq_class_ind.name})")
                                            setattr(eq_class_ind, "defaultSequencePosition", default_pos)
                                        # Store in the positions dict for later relationship building
                                        equipment_class_positions[eq_class_name] = default_pos
                                    else:
                                        # Check if it already has a position set by other means
                                        existing_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
                                        if existing_pos is not None and eq_class_name not in equipment_class_positions:
                                             equipment_class_positions[eq_class_name] = existing_pos
                                             pop_logger.debug(f"Class {eq_class_name} already had sequence position {existing_pos}, adding to tracking.")

                        # Link Equipment to EquipmentClass (FUNCTIONAL per spec)
                        if getattr(equipment_ind, "memberOfClass", None) != eq_class_ind:
                            setattr(equipment_ind, "memberOfClass", eq_class_ind)
                            pop_logger.debug(f"Linking {equipment_ind.name} memberOfClass {eq_class_ind.name}")

                        # Set default sequence position *on the class individual* (FUNCTIONAL per spec)
                        default_pos = DEFAULT_EQUIPMENT_SEQUENCE.get(eq_class_name)
                        if default_pos is not None:
                            existing_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
                            # Assign only if not already set or if forced update is desired
                            if existing_pos is None or existing_pos != default_pos:
                                pop_logger.debug(f"Assigning default sequence position {default_pos} to class {eq_class_name} ({eq_class_ind.name})")
                                setattr(eq_class_ind, "defaultSequencePosition", default_pos)

                    else:
                        pop_logger.error(f"Row {row_num}: Failed to create Equipment individual for ID '{eq_id_str}'.")
                        raise ValueError("Failed to create Equipment individual.") # Fatal for this row

                else:
                    pop_logger.warning(f"Row {row_num}: Could not determine resource. EQUIPMENT_TYPE='{eq_type}', EQUIPMENT_ID='{eq_id_raw}', LINE_NAME='{line_id}'. Skipping row.")
                    failed_rows += 1
                    continue # Skip if we can't identify the main resource

                if not resource_individual or not resource_base_id:
                    pop_logger.error(f"Row {row_num}: Internal error - resource_individual or resource_base_id not set. Skipping row.")
                    failed_rows += 1
                    continue

                # --- Create Material Individual ---
                mat_id = safe_cast(row.get('MATERIAL_ID'), str)
                mat_ind: Optional[Thing] = None
                if mat_id and cls_Material:
                    mat_desc = safe_cast(row.get('SHORT_MATERIAL_ID'), str)
                    mat_labels = [mat_id]
                    if mat_desc: mat_labels.append(mat_desc)
                    mat_ind = get_or_create_individual(cls_Material, mat_id, onto, add_labels=mat_labels)
                    if mat_ind:
                        # Set Material properties
                        prop_materialId = prop_map.get("materialId")
                        if prop_materialId: # Functional
                            if mat_id is not None and getattr(mat_ind, "materialId", None) != mat_id:
                                setattr(mat_ind, "materialId", mat_id)

                        prop_materialDescription = prop_map.get("materialDescription")
                        if prop_materialDescription and mat_desc: # Non-functional
                            if mat_desc not in mat_ind.materialDescription:
                                mat_ind.materialDescription.append(mat_desc)

                        prop_sizeType = prop_map.get("sizeType")
                        if prop_sizeType: # Non-functional
                            size = safe_cast(row.get('SIZE_TYPE'), str)
                            if size and size not in mat_ind.sizeType:
                                 mat_ind.sizeType.append(size)

                        prop_materialUOM = prop_map.get("materialUOM")
                        if prop_materialUOM: # Functional
                            material_uom = safe_cast(row.get('MATERIAL_UOM'), str)
                            if material_uom is not None and getattr(mat_ind, "materialUOM", None) != material_uom:
                                 setattr(mat_ind, "materialUOM", material_uom)

                        prop_standardUOM = prop_map.get("standardUOM")
                        if prop_standardUOM: # Functional
                            uom_st = safe_cast(row.get('UOM_ST'), str) or safe_cast(row.get('UOM_ST_SAP'), str)
                            if uom_st is not None and getattr(mat_ind, "standardUOM", None) != uom_st:
                                 setattr(mat_ind, "standardUOM", uom_st)

                        prop_targetProductUOM = prop_map.get("targetProductUOM")
                        if prop_targetProductUOM: # Functional
                            tp_uom = safe_cast(row.get('TP_UOM'), str)
                            if tp_uom is not None and getattr(mat_ind, "targetProductUOM", None) != tp_uom:
                                 setattr(mat_ind, "targetProductUOM", tp_uom)

                        prop_conversionFactor = prop_map.get("conversionFactor")
                        if prop_conversionFactor: # Functional
                            factor = safe_cast(row.get('PRIMARY_CONV_FACTOR'), float)
                            if factor is not None and getattr(mat_ind, "conversionFactor", None) != factor:
                                 setattr(mat_ind, "conversionFactor", factor)

                # --- Create Production Request Individual ---
                req_id = safe_cast(row.get('PRODUCTION_ORDER_ID'), str)
                req_ind: Optional[Thing] = None
                if req_id and cls_ProductionRequest:
                    req_desc = safe_cast(row.get('PRODUCTION_ORDER_DESC'), str)
                    req_labels = [f"ID:{req_id}"]
                    if req_desc: req_labels.insert(0, req_desc)
                    req_ind = get_or_create_individual(cls_ProductionRequest, req_id, onto, add_labels=req_labels)
                    if req_ind:
                        prop_requestId = prop_map.get("requestId")
                        if prop_requestId: # Functional
                            if req_id is not None and getattr(req_ind, "requestId", None) != req_id:
                                setattr(req_ind, "requestId", req_id)

                        prop_requestDescription = prop_map.get("requestDescription")
                        if prop_requestDescription and req_desc: # Non-functional
                            if req_desc not in req_ind.requestDescription:
                                 req_ind.requestDescription.append(req_desc)

                        prop_requestRate = prop_map.get("requestRate")
                        if prop_requestRate: # Functional
                            rate = safe_cast(row.get('PRODUCTION_ORDER_RATE'), float)
                            if rate is not None and getattr(req_ind, "requestRate", None) != rate:
                                 setattr(req_ind, "requestRate", rate)

                        prop_requestRateUOM = prop_map.get("requestRateUOM")
                        if prop_requestRateUOM: # Functional
                            rate_uom = safe_cast(row.get('PRODUCTION_ORDER_UOM'), str)
                            if rate_uom is not None and getattr(req_ind, "requestRateUOM", None) != rate_uom:
                                 setattr(req_ind, "requestRateUOM", rate_uom)

                        # Link ProductionRequest to Material if needed (NON-FUNCTIONAL)
                        prop_usesMaterialReq = prop_map.get("usesMaterial")
                        if prop_usesMaterialReq and mat_ind:
                             if mat_ind not in req_ind.usesMaterial:
                                 req_ind.usesMaterial.append(mat_ind)


                # --- Create Shift Individual ---
                shift_name = safe_cast(row.get('SHIFT_NAME'), str)
                shift_ind: Optional[Thing] = None
                if shift_name and cls_Shift:
                    shift_labels = [shift_name]
                    shift_ind = get_or_create_individual(cls_Shift, shift_name, onto, add_labels=shift_labels)
                    if shift_ind:
                        # Populate shift details (Functional properties, assign only if needed/missing)
                        prop_shiftId = prop_map.get("shiftId")
                        if prop_shiftId and getattr(shift_ind, "shiftId", None) != shift_name:
                             if shift_name is not None:
                                 setattr(shift_ind, "shiftId", shift_name)

                        prop_shiftStartTime = prop_map.get("shiftStartTime")
                        if prop_shiftStartTime and getattr(shift_ind, "shiftStartTime", None) is None:
                            st = safe_cast(row.get('SHIFT_START_DATE_LOC'), datetime)
                            if st is not None:
                                setattr(shift_ind, "shiftStartTime", st)

                        prop_shiftEndTime = prop_map.get("shiftEndTime")
                        if prop_shiftEndTime and getattr(shift_ind, "shiftEndTime", None) is None:
                            et = safe_cast(row.get('SHIFT_END_DATE_LOC'), datetime)
                            if et is not None:
                                setattr(shift_ind, "shiftEndTime", et)

                        prop_shiftDurationMinutes = prop_map.get("shiftDurationMinutes")
                        if prop_shiftDurationMinutes and getattr(shift_ind, "shiftDurationMinutes", None) is None:
                            dur = safe_cast(row.get('SHIFT_DURATION_MIN'), float)
                            if dur is not None:
                                setattr(shift_ind, "shiftDurationMinutes", dur)


                # --- Create Operational State and Reason Individuals ---
                # OperationalState
                state_desc = safe_cast(row.get('UTIL_STATE_DESCRIPTION'), str)
                state_ind: Optional[Thing] = None
                if state_desc and cls_OperationalState:
                    state_labels = [state_desc]
                    state_ind = get_or_create_individual(cls_OperationalState, state_desc, onto, add_labels=state_labels)
                    if state_ind:
                        prop_stateDescription = prop_map.get("stateDescription")
                        if prop_stateDescription and state_desc: # Non-functional
                             if state_desc not in state_ind.stateDescription:
                                 state_ind.stateDescription.append(state_desc)

                # OperationalReason
                reason_desc = safe_cast(row.get('UTIL_REASON_DESCRIPTION'), str)
                reason_ind: Optional[Thing] = None
                if reason_desc and cls_OperationalReason:
                    reason_labels = [reason_desc]
                    reason_ind = get_or_create_individual(cls_OperationalReason, reason_desc, onto, add_labels=reason_labels)
                    if reason_ind:
                        prop_reasonDescription = prop_map.get("reasonDescription")
                        if prop_reasonDescription and reason_desc: # Non-functional
                             if reason_desc not in reason_ind.reasonDescription:
                                 reason_ind.reasonDescription.append(reason_desc)

                        # Handle AltReasonDescription with language tag
                        prop_altReasonDescription = prop_map.get("altReasonDescription")
                        if prop_altReasonDescription:
                            alt_reason = safe_cast(row.get('UTIL_ALT_LANGUAGE_REASON'), str)
                            if alt_reason:
                                plant_country = safe_cast(row.get('PLANT_COUNTRY_DESCRIPTION'), str)
                                lang_tag = COUNTRY_TO_LANGUAGE.get(plant_country, DEFAULT_LANGUAGE)
                                if lang_tag:
                                    try:
                                        alt_reason_locstr = locstr(alt_reason, lang=lang_tag)
                                        # Append non-functional property, check first
                                        if alt_reason_locstr not in reason_ind.altReasonDescription:
                                            reason_ind.altReasonDescription.append(alt_reason_locstr)
                                            pop_logger.debug(f"Added localized reason '{alt_reason}'@{lang_tag} to {reason_ind.name}")
                                    except Exception as e_loc:
                                        pop_logger.warning(f"Failed to create locstr for alt reason '{alt_reason}': {e_loc}")
                                        # Fallback to plain string
                                        if alt_reason not in reason_ind.altReasonDescription:
                                             reason_ind.altReasonDescription.append(alt_reason)
                                else: # No language mapping found
                                    pop_logger.warning(f"No language mapping for country '{plant_country}', using plain string for alt reason.")
                                    if alt_reason not in reason_ind.altReasonDescription:
                                        reason_ind.altReasonDescription.append(alt_reason)

                        prop_downtimeDriver = prop_map.get("downtimeDriver")
                        if prop_downtimeDriver: # Non-functional
                            dt_driver = safe_cast(row.get('DOWNTIME_DRIVER'), str)
                            if dt_driver and dt_driver not in reason_ind.downtimeDriver:
                                 reason_ind.downtimeDriver.append(dt_driver)

                        prop_changeoverType = prop_map.get("changeoverType")
                        if prop_changeoverType: # Non-functional
                            co_type = safe_cast(row.get('CO_TYPE'), str) or safe_cast(row.get('CO_ORIGINAL_TYPE'), str)
                            if co_type and co_type not in reason_ind.changeoverType:
                                 reason_ind.changeoverType.append(co_type)


                # --- Create Time Interval ---
                start_time = safe_cast(row.get('JOB_START_TIME_LOC'), datetime)
                end_time = safe_cast(row.get('JOB_END_TIME_LOC'), datetime)
                time_interval_ind: Optional[Thing] = None
                if start_time and cls_TimeInterval:
                    # Create a unique TimeInterval using resource, start time, and row number
                    start_time_str = start_time.strftime('%Y%m%dT%H%M%S%f')[:-3] # Milliseconds precision
                    interval_base = f"Interval_{resource_base_id}_{start_time_str}_{row_num}"
                    interval_labels = [f"Interval for {resource_base_id} starting {start_time}"]
                    time_interval_ind = get_or_create_individual(cls_TimeInterval, interval_base, onto, add_labels=interval_labels)
                    if time_interval_ind:
                        prop_startTime = prop_map.get("startTime")
                        if prop_startTime: # Functional
                            if start_time is not None and getattr(time_interval_ind, "startTime", None) != start_time:
                                setattr(time_interval_ind, "startTime", start_time)
                        prop_endTime = prop_map.get("endTime")
                        if prop_endTime and end_time: # Functional
                             if end_time is not None and getattr(time_interval_ind, "endTime", None) != end_time:
                                 setattr(time_interval_ind, "endTime", end_time)
                    else:
                        pop_logger.error(f"Row {row_num}: Failed to create TimeInterval individual.")
                        raise ValueError("Failed to create TimeInterval.") # Fatal for this row
                # Removed the row skipping for missing start_time
                # We'll continue processing even if start_time is missing

                # --- Create Event Record Individual ---
                # Create event_record_base name, handling case where interval_base might not be set
                event_record_base = f"Event_{interval_base if 'interval_base' in locals() else f'Row{row_num}_{resource_base_id}'}"
                event_labels = [f"Event for {resource_base_id} at {start_time if start_time else 'unknown time'}"]
                event_ind = get_or_create_individual(cls_EventRecord, event_record_base, onto, add_labels=event_labels)

                if not event_ind:
                    pop_logger.error(f"Row {row_num}: Failed to create EventRecord individual. Skipping row.")
                    failed_rows += 1
                    continue

                # --- Populate EventRecord Data Properties ---
                prop_operationType = prop_map.get("operationType")
                if prop_operationType: # Non-functional
                    op_type = safe_cast(row.get('OPERA_TYPE'), str)
                    if op_type and op_type not in event_ind.operationType:
                         event_ind.operationType.append(op_type)

                prop_rampUpFlag = prop_map.get("rampUpFlag")
                if prop_rampUpFlag: # Functional
                    ramp_flag = safe_cast(row.get('RAMPUP_FLAG'), bool, default=False)
                    if ramp_flag is not None and getattr(event_ind, "rampUpFlag", None) != ramp_flag:
                         setattr(event_ind, "rampUpFlag", ramp_flag)

                # Time Metrics (Functional)
                prop_reportedDurationMinutes = prop_map.get("reportedDurationMinutes")
                if prop_reportedDurationMinutes:
                    total_time_min = safe_cast(row.get('TOTAL_TIME'), float)
                    if total_time_min is not None and getattr(event_ind, "reportedDurationMinutes", None) != total_time_min:
                         setattr(event_ind, "reportedDurationMinutes", total_time_min)

                time_metric_cols = {
                    "businessExternalTimeMinutes": "BUSINESS_EXTERNAL_TIME",
                    "plantAvailableTimeMinutes": "PLANT_AVAILABLE_TIME",
                    "effectiveRuntimeMinutes": "EFFECTIVE_RUNTIME",
                    "plantDecisionTimeMinutes": "PLANT_DECISION_TIME",
                    "productionAvailableTimeMinutes": "PRODUCTION_AVAILABLE_TIME"
                }
                for prop_name, col_name in time_metric_cols.items():
                    prop_obj = prop_map.get(prop_name)
                    if prop_obj:
                        val = safe_cast(row.get(col_name), float)
                        if val is not None:
                            # Use getattr/setattr for dynamic functional assignment
                            if getattr(event_ind, prop_name, None) != val:
                                 setattr(event_ind, prop_name, val)


                # --- Link EventRecord to other Individuals (Object Properties) ---

                # Link to resource (Line or Equipment) - involvesResource (NON-FUNCTIONAL)
                prop_involvesResource = prop_map.get("involvesResource")
                if prop_involvesResource and resource_individual:
                     if resource_individual not in event_ind.involvesResource:
                         event_ind.involvesResource.append(resource_individual)
                         pop_logger.debug(f"Linked {event_ind.name} involvesResource {resource_individual.name}")

                # Link to ProductionRequest - associatedWithProductionRequest (NON-FUNCTIONAL)
                prop_associatedWithProductionRequest = prop_map.get("associatedWithProductionRequest")
                if prop_associatedWithProductionRequest and req_ind:
                     if req_ind not in event_ind.associatedWithProductionRequest:
                         event_ind.associatedWithProductionRequest.append(req_ind)
                         pop_logger.debug(f"Linked {event_ind.name} associatedWithProductionRequest {req_ind.name}")

                # Link to Material - usesMaterial (NON-FUNCTIONAL)
                prop_usesMaterialEvent = prop_map.get("usesMaterial")
                if prop_usesMaterialEvent and mat_ind:
                     if mat_ind not in event_ind.usesMaterial:
                         event_ind.usesMaterial.append(mat_ind)
                         pop_logger.debug(f"Linked {event_ind.name} usesMaterial {mat_ind.name}")

                # Link to TimeInterval - occursDuring (FUNCTIONAL)
                prop_occursDuring = prop_map.get("occursDuring")
                if prop_occursDuring and time_interval_ind:
                    if time_interval_ind is not None and getattr(event_ind, "occursDuring", None) != time_interval_ind:
                        setattr(event_ind, "occursDuring", time_interval_ind)
                        pop_logger.debug(f"Set functional property occursDuring for {event_ind.name} to {time_interval_ind.name}")

                # Link to Shift - duringShift (FUNCTIONAL)
                prop_duringShift = prop_map.get("duringShift")
                if prop_duringShift and shift_ind:
                    if shift_ind is not None and getattr(event_ind, "duringShift", None) != shift_ind:
                        setattr(event_ind, "duringShift", shift_ind)
                        pop_logger.debug(f"Set functional property duringShift for {event_ind.name} to {shift_ind.name}")

                # Link to OperationalState - eventHasState (FUNCTIONAL)
                prop_eventHasState = prop_map.get("eventHasState")
                if prop_eventHasState and state_ind:
                    if state_ind is not None and getattr(event_ind, "eventHasState", None) != state_ind:
                        setattr(event_ind, "eventHasState", state_ind)
                        pop_logger.debug(f"Set functional property eventHasState for {event_ind.name} to {state_ind.name}")

                # Link to OperationalReason - eventHasReason (FUNCTIONAL)
                prop_eventHasReason = prop_map.get("eventHasReason")
                if prop_eventHasReason and reason_ind:
                    if reason_ind is not None and getattr(event_ind, "eventHasReason", None) != reason_ind:
                        setattr(event_ind, "eventHasReason", reason_ind)
                        pop_logger.debug(f"Set functional property eventHasReason for {event_ind.name} to {reason_ind.name}")

                # Add links to Personnel, ProcessSegment etc. if data/properties exist

                successful_rows += 1

            except Exception as e:
                failed_rows += 1
                pop_logger.error(f"Error processing data row {row_num}: {row if len(str(row)) < 500 else str(row)[:500] + '...'}")
                pop_logger.exception("Exception details:")

    # Log unique equipment class summary
    pop_logger.info("--- Unique Equipment Classes Found During Population ---")
    if created_equipment_class_inds:
        sorted_class_names = sorted(created_equipment_class_inds.keys())
        pop_logger.info(f"Total unique equipment classes found: {len(sorted_class_names)}")
        for class_name in sorted_class_names:
            pop_logger.info(f"  • {class_name}")
    else:
        pop_logger.warning("No EquipmentClass individuals were created during population!")

    # Log equipment class sequence position summary
    if equipment_class_positions:
        pop_logger.info("--- Equipment Class Sequence Position Summary (from population) ---")
        sorted_classes_pos = sorted(equipment_class_positions.items(), key=lambda x: x[1])
        for eq_class, position in sorted_classes_pos:
            pop_logger.info(f"Equipment Class: {eq_class} - Default Sequence Position: {position}")
        pop_logger.info(f"Total equipment classes with sequence positions found: {len(equipment_class_positions)}")
    else:
        pop_logger.warning("No equipment classes with sequence positions were processed or found during population.")

    pop_logger.info(f"Ontology population complete. Successfully processed {successful_rows} rows, failed to process {failed_rows} rows.")
    return failed_rows, created_equipment_class_inds, equipment_class_positions


def setup_equipment_sequence_relationships(onto: Ontology,
                                         equipment_class_positions: Dict[str, int],
                                         defined_classes: Dict[str, ThingClass],
                                         prop_map: Dict[str, Optional[PropertyClass]],
                                         created_equipment_class_inds: Dict[str, Thing]):
    """
    Establish upstream/downstream relationships between equipment *classes* based on sequence positions.
    """
    pop_logger.info("Setting up CLASS-LEVEL equipment sequence relationships based on position...")

    # Get the CLASS-LEVEL properties
    prop_classIsUpstreamOf = prop_map.get("classIsUpstreamOf")
    prop_classIsDownstreamOf = prop_map.get("classIsDownstreamOf")

    if not prop_classIsUpstreamOf:
        pop_logger.error("Cannot establish CLASS-LEVEL sequence relationships: 'classIsUpstreamOf' property not found in prop_map.")
        return
    if not prop_classIsDownstreamOf:
        pop_logger.warning("'classIsDownstreamOf' inverse property not found in prop_map. Only forward relationships will be set.")

    cls_EquipmentClass = defined_classes.get("EquipmentClass")
    if cls_EquipmentClass and cls_EquipmentClass not in prop_classIsUpstreamOf.domain:
         pop_logger.warning(f"Property 'classIsUpstreamOf' ({prop_classIsUpstreamOf}) does not have EquipmentClass in its domain {prop_classIsUpstreamOf.domain}.")
    elif not cls_EquipmentClass:
         pop_logger.warning("EquipmentClass not found in defined_classes, cannot verify classIsUpstreamOf domain.")

    if not created_equipment_class_inds:
        pop_logger.warning("No created EquipmentClass individuals provided. Cannot establish class relationships.")
        return
    if not equipment_class_positions:
         pop_logger.warning("Equipment class positions dictionary is empty. Cannot establish class relationships.")
         return

    sorted_classes = sorted(equipment_class_positions.items(), key=lambda x: x[1])
    if len(sorted_classes) < 2:
        pop_logger.warning("Not enough equipment classes with sequence positions (< 2) to establish relationships.")
        return

    # Create relationships based on sequence order
    relationships_created = 0
    with onto:
        for i in range(len(sorted_classes) - 1):
            upstream_class_name, up_pos = sorted_classes[i]
            downstream_class_name, down_pos = sorted_classes[i + 1]

            upstream_ind = created_equipment_class_inds.get(upstream_class_name)
            downstream_ind = created_equipment_class_inds.get(downstream_class_name)

            if not upstream_ind:
                pop_logger.warning(f"Sequence setup: Upstream class individual '{upstream_class_name}' not found.")
                continue
            if not downstream_ind:
                pop_logger.warning(f"Sequence setup: Downstream class individual '{downstream_class_name}' not found.")
                continue

            pop_logger.debug(f"Found upstream class: {upstream_ind.name} (Pos {up_pos}), downstream class: {downstream_ind.name} (Pos {down_pos})")

            # Set relationships (classIsUpstreamOf is NOT functional per spec)
            try:
                # Check if relationship already exists before appending
                current_downstream = getattr(upstream_ind, "classIsUpstreamOf", []) # Use getattr for safety
                if downstream_ind not in current_downstream:
                    pop_logger.debug(f"Attempting CLASS relationship: {upstream_ind.name} classIsUpstreamOf {downstream_ind.name}")
                    upstream_ind.classIsUpstreamOf.append(downstream_ind) # Use direct access for append
                    pop_logger.debug(f"Set CLASS relationship: {upstream_class_name} ({upstream_ind.name}) classIsUpstreamOf {downstream_class_name} ({downstream_ind.name})")

                    # Explicitly set the inverse relationship if available
                    if prop_classIsDownstreamOf:
                        if upstream_ind not in getattr(downstream_ind, "classIsDownstreamOf", []):
                            downstream_ind.classIsDownstreamOf.append(upstream_ind)
                            pop_logger.debug(f"Set INVERSE CLASS relationship: {downstream_class_name} ({downstream_ind.name}) classIsDownstreamOf {upstream_class_name} ({upstream_ind.name})")

                    relationships_created += 1
                else:
                    pop_logger.debug(f"CLASS relationship already exists: {upstream_class_name} classIsUpstreamOf {downstream_class_name}")

            except Exception as e:
                pop_logger.error(f"Error setting class relationship {upstream_class_name} -> {downstream_class_name}: {e}")

    pop_logger.info(f"Created {relationships_created} CLASS-LEVEL upstream/downstream relationships.")

    # Print relationship summary to stdout
    print("\n=== EQUIPMENT CLASS SEQUENCE RELATIONSHIP REPORT ===")
    if relationships_created > 0:
        print(f"Created {relationships_created} upstream/downstream relationships between Equipment Classes:")
        for i in range(len(sorted_classes) - 1):
            upstream_class_name, _ = sorted_classes[i]
            downstream_class_name, _ = sorted_classes[i + 1]
            if created_equipment_class_inds.get(upstream_class_name) and created_equipment_class_inds.get(downstream_class_name):
                print(f"  {upstream_class_name} → {downstream_class_name}")
    else:
        print("No class-level sequence relationships were created.")
    print(f"Total classes with positions considered: {len(sorted_classes)}")


def setup_equipment_instance_relationships(onto: Ontology,
                                         defined_classes: Dict[str, ThingClass],
                                         prop_map: Dict[str, Optional[PropertyClass]],
                                         equipment_class_positions: Dict[str, int]):
    """
    Establish upstream/downstream relationships between equipment *instances* within the same production line.
    """
    pop_logger.info("Setting up INSTANCE-LEVEL equipment relationships within production lines...")

    # Get the required classes and properties
    cls_Equipment = defined_classes.get("Equipment")
    cls_ProductionLine = defined_classes.get("ProductionLine")
    cls_EquipmentClass = defined_classes.get("EquipmentClass")
    prop_isPartOfProductionLine = prop_map.get("isPartOfProductionLine")
    prop_memberOfClass = prop_map.get("memberOfClass")
    prop_equipmentClassId = prop_map.get("equipmentClassId")
    prop_equipment_isUpstreamOf = prop_map.get("equipmentIsUpstreamOf")
    prop_equipment_isDownstreamOf = prop_map.get("equipmentIsDownstreamOf")

    if not all([cls_Equipment, cls_ProductionLine, cls_EquipmentClass,
                prop_isPartOfProductionLine, prop_memberOfClass, prop_equipmentClassId,
                prop_equipment_isUpstreamOf]):
        pop_logger.error("Missing required classes or properties for equipment instance relationships. Check: Equipment, ProductionLine, EquipmentClass, isPartOfProductionLine, memberOfClass, equipmentClassId, equipmentIsUpstreamOf")
        return

    if not prop_equipment_isDownstreamOf:
        pop_logger.warning("'equipmentIsDownstreamOf' inverse property not found in prop_map. Only forward instance relationships will be set.")

    if cls_Equipment not in prop_equipment_isUpstreamOf.domain:
         pop_logger.warning(f"Property 'equipmentIsUpstreamOf' ({prop_equipment_isUpstreamOf}) does not have Equipment in its domain {prop_equipment_isUpstreamOf.domain}.")

    if not equipment_class_positions:
         pop_logger.warning("Equipment class positions dictionary is empty. Cannot establish instance relationships.")
         return
    sorted_classes = sorted(equipment_class_positions.items(), key=lambda x: x[1])
    if len(sorted_classes) < 2:
        pop_logger.warning("Not enough equipment classes with sequence positions (< 2) to establish instance relationships.")
        return

    # Group equipment instances by line and class name
    pop_logger.debug("Grouping equipment instances by production line and class name...")
    line_equipment_map: Dict[Thing, Dict[str, List[Thing]]] = {} # {line_individual: {class_name_str: [equipment_instances]}}

    for equipment_inst in onto.search(type=cls_Equipment):
        # Get the line(s) this equipment belongs to (Non-functional)
        equipment_lines = getattr(equipment_inst, "isPartOfProductionLine", [])
        if not equipment_lines:
            pop_logger.debug(f"Equipment {equipment_inst.name} is not linked to any ProductionLine. Skipping.")
            continue
        # Assume equipment belongs to only one line for sequencing.
        if len(equipment_lines) > 1:
            pop_logger.warning(f"Equipment {equipment_inst.name} linked to multiple lines: {[l.name for l in equipment_lines]}. Using first line '{equipment_lines[0].name}' for sequencing.")
        equipment_line = equipment_lines[0]
        if not isinstance(equipment_line, cls_ProductionLine):
            pop_logger.warning(f"Equipment {equipment_inst.name} linked to non-ProductionLine '{equipment_line}'. Skipping.")
            continue

        # Get the EquipmentClass this equipment belongs to (Functional)
        equipment_class_ind = getattr(equipment_inst, "memberOfClass", None)
        if not equipment_class_ind or not isinstance(equipment_class_ind, cls_EquipmentClass):
              pop_logger.debug(f"Equipment {equipment_inst.name} is not linked to an EquipmentClass. Skipping.")
              continue

        # Get the class name string from the EquipmentClass individual (Functional)
        class_name_str = getattr(equipment_class_ind, "equipmentClassId", None)
        if not class_name_str:
            pop_logger.warning(f"EquipmentClass {equipment_class_ind.name} (linked from {equipment_inst.name}) is missing 'equipmentClassId'. Skipping.")
            continue

        # Check if this class name is in our sequence map
        if class_name_str not in equipment_class_positions:
              pop_logger.debug(f"Equipment {equipment_inst.name}'s class '{class_name_str}' not in sequence map. Skipping.")
              continue

        # Add equipment to the map
        if equipment_line not in line_equipment_map:
            line_equipment_map[equipment_line] = {}
        if class_name_str not in line_equipment_map[equipment_line]:
            line_equipment_map[equipment_line][class_name_str] = []

        if equipment_inst not in line_equipment_map[equipment_line][class_name_str]:
            line_equipment_map[equipment_line][class_name_str].append(equipment_inst)
            pop_logger.debug(f"Mapped Equipment {equipment_inst.name} to Line {equipment_line.name} under Class '{class_name_str}'")

    # Create instance-level relationships within each line
    total_relationships = 0
    line_relationship_counts: Dict[str, int] = {}
    pop_logger.info(f"Found {len(line_equipment_map)} lines with sequenced equipment.")

    with onto:
        for line_ind, class_equipment_map in line_equipment_map.items():
            line_id_str = getattr(line_ind, "lineId", line_ind.name)
            line_relationships = 0
            pop_logger.debug(f"Processing equipment instance relationships for line: {line_id_str}")

            # For each pair of adjacent equipment classes in the sequence
            for i in range(len(sorted_classes) - 1):
                upstream_class_name, _ = sorted_classes[i]
                downstream_class_name, _ = sorted_classes[i + 1]

                upstream_equipment_on_line = class_equipment_map.get(upstream_class_name, [])
                downstream_equipment_on_line = class_equipment_map.get(downstream_class_name, [])

                if not upstream_equipment_on_line or not downstream_equipment_on_line:
                    continue # Skip pair if one class has no instances on this line

                # Create relationships between all upstream instances and all downstream instances ON THIS LINE
                for upstream_eq in upstream_equipment_on_line:
                    for downstream_eq in downstream_equipment_on_line:
                        # equipmentIsUpstreamOf is NON-FUNCTIONAL per spec, use append
                        try:
                            current_downstream_rels = getattr(upstream_eq, "equipmentIsUpstreamOf", [])
                            if downstream_eq not in current_downstream_rels:
                                pop_logger.debug(f"Attempting INSTANCE relationship: {upstream_eq.name} equipmentIsUpstreamOf {downstream_eq.name}")
                                upstream_eq.equipmentIsUpstreamOf.append(downstream_eq)

                                # Explicitly set the inverse relationship
                                if prop_equipment_isDownstreamOf:
                                    if upstream_eq not in getattr(downstream_eq, "equipmentIsDownstreamOf", []):
                                        downstream_eq.equipmentIsDownstreamOf.append(upstream_eq)
                                        pop_logger.debug(f"Set INVERSE INSTANCE relationship: {downstream_eq.name} equipmentIsDownstreamOf {upstream_eq.name}")

                                line_relationships += 1
                                pop_logger.debug(f"Set INSTANCE relationship: {upstream_eq.name} equipmentIsUpstreamOf {downstream_eq.name} on line {line_id_str}")

                        except Exception as e:
                            pop_logger.error(f"Error setting instance relationship {upstream_eq.name} -> {downstream_eq.name} on line {line_id_str}: {e}")

            # Record relationships for this line
            if line_relationships > 0:
                line_relationship_counts[line_id_str] = line_relationships
                total_relationships += line_relationships
                pop_logger.info(f"Created {line_relationships} instance relationships for line {line_id_str}.")

    # Print summary report
    print("\n=== EQUIPMENT INSTANCE RELATIONSHIP REPORT ===")
    if total_relationships > 0:
        pop_logger.info(f"Created {total_relationships} equipment instance relationships across {len(line_relationship_counts)} production lines.")
        print(f"Created {total_relationships} equipment instance relationships on {len(line_relationship_counts)} lines:")
        for line_id_str, count in sorted(line_relationship_counts.items()):
            print(f"  Line {line_id_str}: {count} relationships")
    else:
        pop_logger.warning("No equipment instance relationships were created.")
        print("No equipment instance relationships could be established.")
        print("Possible reasons: Equipment not linked to lines/classes, missing sequence positions, or no adjacent equipment found on the same line.")

#======================================================================#
#               create_ontology.py Module Code (Main)                #
#======================================================================#

def read_data(data_file_path: str) -> List[Dict[str, str]]:
    """Reads the operational data CSV file."""
    main_logger.info(f"Reading data file: {data_file_path}")
    data_rows: List[Dict[str, str]] = []
    try:
        with open(data_file_path, mode='r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            data_rows = list(reader)
            main_logger.info(f"Successfully read {len(data_rows)} data rows.")
            return data_rows
    except FileNotFoundError:
        main_logger.error(f"Data file not found: {data_file_path}")
        raise
    except Exception as e:
        main_logger.error(f"Error reading data file {data_file_path}: {e}")
        raise
    return [] # Return empty list on error if not raising


def generate_reasoning_report(onto: Ontology,
                              pre_stats: Dict[str, int],
                              post_stats: Dict[str, int],
                              inconsistent_classes: List[ThingClass],
                              inferred_hierarchy: Dict[str, Dict[str, List[str]]],
                              inferred_properties: Dict[str, List[str]],
                              inferred_individuals: Dict[str, Dict[str, Any]],
                              use_reasoner: bool
                             ) -> Tuple[str, bool]:
    """
    Generates a structured report from reasoning results. Returns report string and has_issues flag.
    """
    report_lines = []
    has_issues = False

    def add_section(title):
        report_lines.extend(["\n" + "="*80, f"{title}", "="*80])

    # 1. Executive Summary
    add_section("REASONING REPORT EXECUTIVE SUMMARY")
    if inconsistent_classes:
        has_issues = True
        report_lines.append("❌ ONTOLOGY STATUS: Inconsistent")
        report_lines.append(f"   Found {len(inconsistent_classes)} inconsistent classes (see details below)")
    else:
        report_lines.append("✅ ONTOLOGY STATUS: Consistent")

    class_diff = post_stats['classes'] - pre_stats['classes']
    prop_diff = (post_stats['object_properties'] - pre_stats['object_properties'] +
                 post_stats['data_properties'] - pre_stats['data_properties'])
    ind_diff = post_stats['individuals'] - pre_stats['individuals']
    report_lines.extend([
        f"\nStructural Changes (Post-Reasoning vs Pre-Reasoning):",
        f"  • Classes: {class_diff:+d}", f"  • Properties (Obj + Data): {prop_diff:+d}", f"  • Individuals: {ind_diff:+d}"
    ])
    inferences_made = bool(inferred_hierarchy or inferred_properties or inferred_individuals)
    report_lines.append(f"\nInferences Made: {'Yes' if inferences_made else 'No'}")

    # 2. Detailed Statistics
    add_section("DETAILED STATISTICS")
    report_lines.extend([
        "\nPre-Reasoning:",
        f"  • Classes: {pre_stats['classes']}", f"  • Object Properties: {pre_stats['object_properties']}",
        f"  • Data Properties: {pre_stats['data_properties']}", f"  • Individuals: {pre_stats['individuals']}",
        "\nPost-Reasoning:",
        f"  • Classes: {post_stats['classes']}", f"  • Object Properties: {post_stats['object_properties']}",
        f"  • Data Properties: {post_stats['data_properties']}", f"  • Individuals: {post_stats['individuals']}"
    ])

    # 3. Consistency Issues
    if inconsistent_classes:
        add_section("CONSISTENCY ISSUES")
        report_lines.append("\nInconsistent Classes:")
        for cls in inconsistent_classes: report_lines.append(f"  • {cls.name} ({cls.iri})")
        has_issues = True

    # 4. Inferred Knowledge
    add_section("INFERRED KNOWLEDGE")
    if inferred_hierarchy:
        report_lines.append("\nClass Hierarchy Changes:")
        for parent, data in inferred_hierarchy.items():
            if data.get('subclasses') or data.get('equivalent'):
                report_lines.append(f"\n  Class: {parent}")
                if data.get('subclasses'):
                    report_lines.append("    ↳ Inferred Subclasses:")
                    for sub in data['subclasses']: report_lines.append(f"        • {sub}")
                if data.get('equivalent'):
                    report_lines.append(f"    ≡ Inferred Equivalent Classes: {', '.join(data['equivalent'])}")
    else: report_lines.append("\nNo new class hierarchy relationships inferred.")

    if inferred_properties:
        report_lines.append("\nInferred Property Characteristics:")
        for prop, chars in inferred_properties.items():
            report_lines.append(f"\n  Property: {prop}")
            for char in chars: report_lines.append(f"    • {char}")
    else: report_lines.append("\nNo new property characteristics inferred.")

    if inferred_individuals:
        report_lines.append("\nIndividual Inferences:")
        for ind_name, data in inferred_individuals.items():
            report_lines.append(f"\n  Individual: {ind_name}")
            if data.get('types'):
                report_lines.append("    Inferred Types:")
                for t in data['types']: report_lines.append(f"      • {t}")
            if data.get('properties'):
                report_lines.append("    Inferred Property Values:")
                for p, vals in data['properties'].items():
                     report_lines.append(f"      • {p}: {', '.join(vals)}") # vals are pre-formatted
    else: report_lines.append("\nNo new individual types or property values inferred.")

    # 5. Recommendations
    add_section("RECOMMENDATIONS")
    recommendations = []
    if inconsistent_classes:
        recommendations.append("❗ HIGH PRIORITY: Resolve inconsistencies listed above.")
    if not inconsistent_classes and not inferences_made:
        recommendations.append("⚠️ No inferences made - Ontology is consistent but may lack richness. Consider adding more specific axioms.")
        has_issues = True
    if class_diff == 0 and prop_diff == 0 and ind_diff == 0 and use_reasoner: # Check use_reasoner flag
         recommendations.append("ℹ️ No structural changes after reasoning - verify if this is expected.")
    if recommendations:
        report_lines.extend(["\n" + rec for rec in recommendations])
    else: report_lines.append("\nNo critical issues or major inference gaps found.")

    return "\n".join(report_lines), has_issues


def main_ontology_generation(spec_file_path: str,
                             data_file_path: str,
                             output_owl_path: str,
                             ontology_iri: str = DEFAULT_ONTOLOGY_IRI,
                             save_format: str = "rdfxml",
                             use_reasoner: bool = False,
                             world_db_path: Optional[str] = None) -> bool:
    """
    Main function to generate the ontology. Returns True on success, False on failure.
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

    world: Optional[World] = None # Define world variable outside try block

    try:
        # 1. Parse Specification
        specification = parse_specification(spec_file_path)
        if not specification:
            main_logger.error("Specification parsing failed or resulted in empty spec. Aborting.")
            return False

        # 2. Create Ontology World and Ontology Object
        if world_db_path:
            main_logger.info(f"Initializing persistent World at: {world_db_path}")
            db_dir = os.path.dirname(world_db_path)
            if db_dir and not os.path.exists(db_dir):
                 os.makedirs(db_dir, exist_ok=True)
                 main_logger.info(f"Created directory for world DB: {db_dir}")
            world = World(filename=world_db_path)
            onto = world.get_ontology(ontology_iri).load()
            main_logger.info(f"Ontology object obtained from persistent world: {onto}")
        else:
            main_logger.info("Initializing in-memory World.")
            world = World() # Create a fresh world
            onto = world.get_ontology(ontology_iri)
            main_logger.info(f"Ontology object created in memory: {onto}")

        # 3. Define Ontology Structure (TBox)
        defined_classes, defined_properties, property_is_functional = define_ontology_structure(onto, specification)
        if not defined_classes:
            main_logger.warning("Ontology structure definition resulted in no classes. Population might be empty.")

        # 4. Read Operational Data
        data_rows = read_data(data_file_path)

        # 5. Populate Ontology (ABox)
        population_successful = True
        failed_rows_count = 0
        created_eq_classes = {}
        eq_class_positions = {}

        if not data_rows:
            main_logger.warning("No data rows read from data file. Ontology will be populated with structure only.")
        else:
            try:
                failed_rows_count, created_eq_classes, eq_class_positions = populate_ontology_from_data(
                    onto, data_rows, defined_classes, defined_properties, property_is_functional
                )
                if failed_rows_count == len(data_rows) and len(data_rows) > 0:
                    main_logger.error(f"Population failed for all {len(data_rows)} data rows.")
                    population_successful = False
                elif failed_rows_count > 0:
                    main_logger.warning(f"Population completed with {failed_rows_count} out of {len(data_rows)} failed rows.")
                else:
                    main_logger.info(f"Population completed successfully for all {len(data_rows)} rows.")

                if not created_eq_classes: main_logger.warning("Population finished, but NO EquipmentClass individuals were created or found.")
                else: main_logger.info(f"Population found/created {len(created_eq_classes)} unique EquipmentClass individuals.")
                if not eq_class_positions: main_logger.warning("Population finished, but NO sequence positions were assigned to EquipmentClasses.")
                else: main_logger.info(f"Population assigned sequence positions to {len(eq_class_positions)} EquipmentClasses.")

            except Exception as pop_exc:
                main_logger.error(f"Critical error during population: {pop_exc}", exc_info=True)
                population_successful = False

        # --- Setup Sequence Relationships AFTER population ---
        if population_successful and created_eq_classes and eq_class_positions:
            main_logger.info("Proceeding to setup sequence relationships...")
            try:
                setup_equipment_sequence_relationships(onto, eq_class_positions, defined_classes, defined_properties, created_eq_classes)
                setup_equipment_instance_relationships(onto, defined_classes, defined_properties, eq_class_positions)
            except Exception as seq_exc:
                main_logger.error(f"Error during sequence relationship setup: {seq_exc}", exc_info=True)
                # Continue, but log error
        elif population_successful:
            main_logger.warning("Skipping sequence relationship setup because no EquipmentClass individuals or positions were generated during population.")
        else:
             main_logger.warning("Skipping sequence relationship setup due to population failure.")


        # 6. Apply Reasoning (Optional)
        reasoning_successful = True
        if use_reasoner and population_successful:
            main_logger.info("Applying reasoner (ensure HermiT or compatible reasoner is installed)...")
            try:
                with onto:
                    pre_stats = {
                        'classes': len(list(onto.classes())), 'object_properties': len(list(onto.object_properties())),
                        'data_properties': len(list(onto.data_properties())), 'individuals': len(list(onto.individuals()))
                    }
                    main_logger.info("Starting reasoning process...")
                    reasoning_start_time = timing.time()
                    sync_reasoner(infer_property_values=True, debug=0)
                    reasoning_end_time = timing.time()
                    main_logger.info(f"Reasoning finished in {reasoning_end_time - reasoning_start_time:.2f} seconds.")

                    # Collect results
                    inconsistent = list(default_world.inconsistent_classes())
                    inferred_hierarchy = {}
                    inferred_properties = {}
                    inferred_individuals = {}
                    # Simplified post-reasoning state collection (as before)
                    for cls in onto.classes():
                         current_subclasses = set(cls.subclasses())
                         inferred_subs = [sub.name for sub in current_subclasses]
                         equivalent_classes = [eq.name for eq in cls.equivalent_to if eq != cls and isinstance(eq, ThingClass)]
                         if inferred_subs or equivalent_classes:
                             inferred_hierarchy[cls.name] = {'subclasses': inferred_subs, 'equivalent': equivalent_classes}

                    inferrable_chars = {
                         'FunctionalProperty': FunctionalProperty, 'InverseFunctionalProperty': InverseFunctionalProperty,
                         'TransitiveProperty': TransitiveProperty, 'SymmetricProperty': SymmetricProperty,
                         'AsymmetricProperty': AsymmetricProperty, 'ReflexiveProperty': ReflexiveProperty,
                         'IrreflexiveProperty': IrreflexiveProperty,
                    }
                    for prop in list(onto.object_properties()) + list(onto.data_properties()):
                         inferred_chars_for_prop = [char_name for char_name, char_class in inferrable_chars.items() if char_class in prop.is_a]
                         if inferred_chars_for_prop: inferred_properties[prop.name] = inferred_chars_for_prop

                    main_logger.info("Collecting simplified individual inferences (post-reasoning state).")
                    for ind in onto.individuals():
                         current_types = [c.name for c in ind.is_a if c is not Thing]
                         current_props = {}
                         for prop in list(onto.object_properties()) + list(onto.data_properties()):
                             try:
                                 values = getattr(ind, prop.python_name, [])
                                 if not isinstance(values, list): values = [values] if values is not None else []
                                 if values:
                                     formatted_values = []
                                     for v in values:
                                         if isinstance(v, Thing): formatted_values.append(v.name)
                                         elif isinstance(v, locstr): formatted_values.append(f'"{v}"@{v.lang}')
                                         else: formatted_values.append(repr(v))
                                     if formatted_values: current_props[prop.name] = formatted_values
                             except Exception: continue # Ignore props not applicable
                         if current_types or current_props:
                             inferred_individuals[ind.name] = {'types': current_types, 'properties': current_props}


                    post_stats = {
                        'classes': len(list(onto.classes())), 'object_properties': len(list(onto.object_properties())),
                        'data_properties': len(list(onto.data_properties())), 'individuals': len(list(onto.individuals()))
                    }
                    report, has_issues = generate_reasoning_report(onto, pre_stats, post_stats, inconsistent, inferred_hierarchy, inferred_properties, inferred_individuals, use_reasoner)
                    main_logger.info("\nReasoning Report:\n" + report)

                    if has_issues or inconsistent:
                        main_logger.warning("Reasoning completed but potential issues or inconsistencies were identified.")
                        if inconsistent: reasoning_successful = False
                    else: main_logger.info("Reasoning completed successfully with no inconsistencies identified.")

            except OwlReadyInconsistentOntologyError:
                main_logger.error("REASONING FAILED: Ontology is inconsistent!")
                reasoning_successful = False
                try:
                    current_world = world if world_db_path else default_world
                    inconsistent = list(current_world.inconsistent_classes())
                    main_logger.error(f"Inconsistent classes detected: {[c.name for c in inconsistent]}")
                except Exception as e_inc: main_logger.error(f"Could not retrieve inconsistent classes: {e_inc}")
            except NameError as ne:
                 if "sync_reasoner" in str(ne): main_logger.error("Reasoning failed: Reasoner not found. Ensure Java/HermiT are installed.")
                 else: main_logger.error(f"Unexpected NameError during reasoning: {ne}")
                 reasoning_successful = False
            except Exception as e:
                main_logger.error(f"An error occurred during reasoning: {e}", exc_info=True)
                reasoning_successful = False

        # 7. Save Ontology
        should_save = population_successful and (not use_reasoner or reasoning_successful)
        final_output_path = output_owl_path
        if not should_save:
             main_logger.error("Ontology generation encountered errors (population or reasoning). Ontology will NOT be saved to the primary output file.")
             debug_output_path = output_owl_path.replace(".owl", "_debug.owl")
             if debug_output_path == output_owl_path: # Avoid overwriting if extension isn't .owl
                 debug_output_path += "_debug"
             main_logger.info(f"Attempting to save potentially problematic ontology to: {debug_output_path}")
             final_output_path = debug_output_path
             should_save = True # Force save to debug file

        if should_save:
            main_logger.info(f"Saving ontology to {final_output_path} in '{save_format}' format...")
            try:
                onto.save(file=final_output_path, format=save_format)
                main_logger.info("Ontology saved successfully.")
            except Exception as save_err:
                main_logger.error(f"Failed to save ontology to {final_output_path}: {save_err}", exc_info=True)
                return False # Saving failed

        # Overall success is true if we reached here without returning False
        return should_save # Will be True if saved, potentially to debug file

    except Exception as e:
        main_logger.exception("A critical error occurred during the overall ontology generation process.")
        return False

    finally:
        # Removed world cleanup logic as requested
        end_time = timing.time()
        main_logger.info(f"--- Ontology Generation Finished ---")
        main_logger.info(f"Total time: {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an OWL ontology from specification and data CSV files.")
    parser.add_argument("spec_file", help="Path to the ontology specification CSV file (e.g., opera_spec.csv).")
    parser.add_argument("data_file", help="Path to the operational data CSV file (e.g., sample_data.csv).")
    parser.add_argument("output_file", help="Path to save the generated OWL ontology file (e.g., manufacturing.owl).")
    parser.add_argument("--iri", default=DEFAULT_ONTOLOGY_IRI, help=f"Base IRI for the ontology (default: {DEFAULT_ONTOLOGY_IRI}).")
    parser.add_argument("--format", default="rdfxml", choices=["rdfxml", "ntriples", "nquads", "owlxml"], help="Format for saving the ontology (default: rdfxml).")
    parser.add_argument("--reasoner", action="store_true", help="Run the reasoner after population.")
    parser.add_argument("--worlddb", default=None, help="Path to use/create a persistent SQLite world database (e.g., my_ontology.sqlite3).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress INFO level logging.")

    args = parser.parse_args()

    # Setup Logging Level
    log_level = logging.INFO
    if args.verbose: log_level = logging.DEBUG
    elif args.quiet: log_level = logging.WARNING

    # Configure logging
    root_logger_instance = logging.getLogger()
    for handler in root_logger_instance.handlers[:]: root_logger_instance.removeHandler(handler)
    logging.basicConfig(level=log_level, format=LOG_FORMAT, stream=sys.stdout)
    logging.getLogger().setLevel(log_level) # Ensure root logger level is set
    for handler in logging.getLogger().handlers: handler.setLevel(log_level) # Ensure handler level is set

    main_logger.info("Logging configured.")
    if args.verbose: main_logger.info("Verbose logging enabled (DEBUG level).")
    elif args.quiet: main_logger.info("Quiet logging enabled (WARNING level).")
    else: main_logger.info("Standard logging enabled (INFO level).")

    # Execute main function
    success = main_ontology_generation(
        args.spec_file, args.data_file, args.output_file,
        args.iri, args.format, args.reasoner, args.worlddb
    )

    # Exit with appropriate code
    if success:
        main_logger.info("Ontology generation process completed.")
        sys.exit(0)
    else:
        main_logger.error("Ontology generation process failed or encountered errors.")
        sys.exit(1)