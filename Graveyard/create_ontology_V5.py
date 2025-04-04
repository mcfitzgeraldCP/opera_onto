# -*- coding: utf-8 -*-
# Combined and Updated Ontology Generation Code (v4 - Fixes & Enhancements)

# ... (Keep imports and Configuration sections as they are) ...
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
from decimal import Decimal, InvalidOperation # Added for safe_cast if needed
from dateutil import parser as dateutil_parser
from dateutil.parser import ParserError # Import the specific error

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
#              ontology_definition.py Module Code                      #
#======================================================================#

# ... (Keep the ontology_definition.py Module Code section as it is) ...
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
#             ontology_population.py Module Code                       #
#======================================================================#

# --- Population Helper Functions ---

def parse_equipment_class(equipment_name: Optional[str]) -> Optional[str]:
    """
    Parses the EquipmentClass from the EQUIPMENT_NAME.
    Rules:
    1. Extracts the part after the last underscore
    2. Removes trailing digits from class name to handle instance identifiers
    3. Validates the resulting class name has letters
    4. Falls back to appropriate alternatives if validation fails

    Examples:
    - FIPCO009_Filler -> Filler
    - FIPCO009_Filler2 -> Filler
    - FIPCO009_CaseFormer3 -> CaseFormer
    - FIPCO009_123 -> FIPCO009 (fallback to part before underscore if after is all digits)
    """
    if not equipment_name or not isinstance(equipment_name, str):
        return None

    if '_' in equipment_name:
        parts = equipment_name.split('_')
        class_part = parts[-1]
        
        # Try to extract base class name by removing trailing digits
        base_class = re.sub(r'\d+$', '', class_part)
        
        # Validate the base class name
        if base_class and re.search(r'[a-zA-Z]', base_class):
            pop_logger.debug(f"Parsed equipment class '{base_class}' from '{equipment_name}' (original part: '{class_part}')")
            return base_class
        else:
            # If stripping digits results in empty/invalid class, try the part before underscore
            if len(parts) > 1 and re.search(r'[a-zA-Z]', parts[-2]):
                fallback_class = parts[-2]
                pop_logger.warning(f"Class part '{class_part}' became invalid after stripping digits. Using fallback from previous part: '{fallback_class}'")
                return fallback_class
            else:
                # Last resort: use original class_part if it has letters, otherwise whole name
                if re.search(r'[a-zA-Z]', class_part):
                    pop_logger.warning(f"Using original class part '{class_part}' as class name (could not extract better alternative)")
                    return class_part
                else:
                    pop_logger.warning(f"No valid class name found in parts of '{equipment_name}'. Using full name as class.")
                    return equipment_name

    # No underscore case
    if re.search(r'[a-zA-Z]', equipment_name):
        # If the full name has letters, try to extract base class by removing trailing digits
        base_class = re.sub(r'\d+$', '', equipment_name)
        if base_class and re.search(r'[a-zA-Z]', base_class):
            pop_logger.debug(f"Extracted base class '{base_class}' from non-underscore name '{equipment_name}'")
            return base_class
        else:
            pop_logger.debug(f"Using full name '{equipment_name}' as class (no underscore, has letters)")
            return equipment_name
    else:
        pop_logger.warning(f"Equipment name '{equipment_name}' contains no letters. Using as is.")
        return equipment_name

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
            # Handle potential floats in data like '224.0' -> 224
            # Also handle direct integers or strings representing integers
            try:
                 return int(float(value_str))
            except ValueError:
                 # Maybe it was already an int disguised as string?
                 return int(value_str)
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
                return None # Explicitly return None for uninterpretable bools
        if target_type is datetime:
            # --- Use dateutil.parser for robust parsing ---
            try:
                # No need for extensive pre-cleaning or format list with dateutil
                # It handles various formats, including spaces and timezones
                parsed_dt = dateutil_parser.parse(value_str)

                # dateutil returns an AWARE datetime if offset is present.
                # owlready2 stores naive datetimes.
                # Maintain existing behavior: make it naive (loses original offset info).
                if parsed_dt.tzinfo:
                    pop_logger.debug(f"Parsed datetime {original_value_repr} with timezone {parsed_dt.tzinfo}, storing as naive datetime.")
                    parsed_dt = parsed_dt.replace(tzinfo=None)
                else:
                     pop_logger.debug(f"Parsed datetime {original_value_repr} without timezone, storing as naive datetime.")

                pop_logger.debug(f"Successfully parsed datetime {original_value_repr} using dateutil -> {parsed_dt}")
                return parsed_dt

            except (ParserError, ValueError, TypeError) as e: # Catch errors from dateutil and potential downstream issues
                pop_logger.warning(f"Could not parse datetime string {original_value_repr} using dateutil parser: {e}")
                return default
            except Exception as e: # Catch any other unexpected errors
                 pop_logger.error(f"Unexpected error parsing datetime {original_value_repr} with dateutil: {e}", exc_info=False)
                 return default
            # --- End of dateutil parsing block ---

        if target_type is date:
             try:
                 # Try ISO first
                 return date.fromisoformat(value_str) # Assumes YYYY-MM-DD
             except ValueError:
                  # Try other common formats if needed
                  try:
                      dt_obj = datetime.strptime(value_str, "%m/%d/%Y") # Example alternative
                      return dt_obj.date()
                  except ValueError:
                      pop_logger.warning(f"Could not parse date string {original_value_repr} as ISO or m/d/Y date.")
                      return default
        if target_type is time:
             try:
                 # Try ISO first
                 return time.fromisoformat(value_str) # Assumes HH:MM:SS[.ffffff][+/-HH:MM]
             except ValueError:
                  # Try other common formats if needed
                  try:
                      dt_obj = datetime.strptime(value_str, "%H:%M:%S") # Just H:M:S
                      return dt_obj.time()
                  except ValueError:
                      pop_logger.warning(f"Could not parse time string {original_value_repr} as ISO or H:M:S time.")
                      return default

        # General cast attempt for types not explicitly handled above (e.g., locstr handled by owlready2)
        if target_type is locstr: # Let owlready2 handle locstr creation later
            return value_str

        # Final fallback cast attempt
        return target_type(value_str)

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
    if individual_name_base is None or str(individual_name_base).strip() == '':
        pop_logger.warning(f"Cannot get/create individual with empty base name for class {onto_class.name if onto_class else 'None'}")
        return None
    if not onto_class:
        pop_logger.error(f"Cannot get/create individual: onto_class parameter is None for base name '{individual_name_base}'.")
        return None

    # 1. Sanitize the base name
    # Convert to string and strip whitespace
    name_str = str(individual_name_base).strip()
    # Replace spaces and common problematic chars with underscore
    safe_base = re.sub(r'\s+|[<>:"/\\|?*#%\']', '_', name_str)
    # Remove any remaining non-alphanumeric, non-hyphen, non-underscore chars (allows periods)
    safe_base = re.sub(r'[^\w\-._]', '', safe_base)
    # Ensure it doesn't start with a number or hyphen (common restriction)
    if safe_base and (safe_base[0].isdigit() or safe_base[0] == '-'):
        safe_base = "_" + safe_base
    # Check if empty after sanitization
    if not safe_base:
        fallback_hash = abs(hash(name_str)) # Hash the original string
        safe_base = f"UnnamedData_{fallback_hash}"
        pop_logger.warning(f"Sanitized name for '{name_str}' became empty or invalid. Using fallback: {safe_base}")

    # 2. Create the class-specific, sanitized name
    final_name = f"{onto_class.name}_{safe_base}"

    # 3. Check if individual exists using namespace search
    individual = onto.search_one(iri=f"{onto.base_iri}{final_name}")

    if individual:
        # Check if the existing individual is of the correct type (or a subclass)
        if isinstance(individual, onto_class):
            # Optionally add labels even if retrieved
            if add_labels:
                current_labels = individual.label
                for lbl in add_labels:
                    lbl_str = safe_cast(lbl, str)
                    if lbl_str and lbl_str not in current_labels:
                            individual.label.append(lbl_str)
            return individual
        else:
            # This is a serious issue - IRI collision with different types
            pop_logger.error(f"IRI collision: Individual '{final_name}' ({individual.iri}) exists but is not of expected type {onto_class.name} (or its subclass). It has type(s): {individual.is_a}. Cannot proceed reliably for this individual.")
            # Decide how to handle: raise error, return None, or try alternative naming?
            # Raising an error might be safest to prevent corrupting the ontology.
            raise TypeError(f"IRI collision: {final_name} exists with incompatible type(s) {individual.is_a} (expected {onto_class.name}).")
            # return None # Alternative: Skip this individual

    # 4. Create the new individual
    try:
        pop_logger.debug(f"Creating new individual '{final_name}' of class {onto_class.name}")
        # Use the final_name directly - owlready2 handles IRI creation with the namespace
        new_individual = onto_class(final_name, namespace=onto)

        # Add labels if provided
        if add_labels:
            for lbl in add_labels:
                lbl_str = safe_cast(lbl, str)
                if lbl_str: new_individual.label.append(lbl_str)

        return new_individual
    except Exception as e:
        pop_logger.error(f"Failed to create individual '{final_name}' of class {onto_class.name}: {e}")
        return None

def _set_property_value(individual: Thing, prop: PropertyClass, value: Any, is_functional: bool):
    """Helper to set functional or non-functional properties, checking existence first."""
    if value is None: return # Don't set None values

    prop_name = prop.python_name # Use Python name for attribute access

    try:
        if is_functional:
            # Functional: Use setattr, potentially overwriting. Check if different first.
            current_value = getattr(individual, prop_name, None)
            # Handle comparison carefully, especially for complex types like lists/individuals
            # Simple direct comparison works for primitives and owlready individuals/locstr
            if current_value != value:
                setattr(individual, prop_name, value)
                pop_logger.debug(f"Set functional property {individual.name}.{prop.name} = {repr(value)}")
        else:
            # Non-Functional: Use append, check if value already exists.
            current_values = getattr(individual, prop_name, [])
            if not isinstance(current_values, list): # Ensure it's a list for append
                 current_values = [current_values] if current_values is not None else []

            if value not in current_values:
                 # owlready handles adding to the list via direct attribute access
                 getattr(individual, prop_name).append(value)
                 pop_logger.debug(f"Appended non-functional property {individual.name}.{prop.name} = {repr(value)}")

    except Exception as e:
        pop_logger.error(f"Error setting property '{prop.name}' on individual '{individual.name}' with value '{repr(value)}': {e}", exc_info=False)


# --- Data Processing Functions ---

class PopulationContext:
    """Holds references to ontology elements needed during population."""
    def __init__(self, onto: Ontology, defined_classes: Dict[str, ThingClass], defined_properties: Dict[str, PropertyClass], property_is_functional: Dict[str, bool]):
        self.onto = onto
        self.classes = defined_classes
        self.props = defined_properties
        self.is_functional = property_is_functional

    def get_class(self, name: str) -> Optional[ThingClass]:
        cls = self.classes.get(name)
        if not cls: pop_logger.error(f"Essential class '{name}' not found in defined_classes.")
        return cls

    def get_prop(self, name: str) -> Optional[PropertyClass]:
        prop = self.props.get(name)
        # Warning for missing props is handled during initial check, less noise here
        # if not prop: pop_logger.warning(f"Property '{name}' not found in defined_properties.")
        return prop

    def set_prop(self, individual: Thing, prop_name: str, value: Any):
        """Safely sets a property value using the context."""
        prop = self.get_prop(prop_name)
        if prop and individual:
            is_func = self.is_functional.get(prop_name, False) # Default to non-functional if not specified
            _set_property_value(individual, prop, value, is_func)

def process_asset_hierarchy(row: Dict[str, Any], context: PopulationContext) -> Tuple[Optional[Thing], Optional[Thing], Optional[Thing], Optional[Thing]]:
    """Processes Plant, Area, ProcessCell, ProductionLine from a row."""
    # Get Classes
    cls_Plant = context.get_class("Plant")
    cls_Area = context.get_class("Area")
    cls_ProcessCell = context.get_class("ProcessCell")
    cls_ProductionLine = context.get_class("ProductionLine")
    if not all([cls_Plant, cls_Area, cls_ProcessCell, cls_ProductionLine]): return None, None, None, None # Abort if essential classes missing

    # Plant
    plant_id = safe_cast(row.get('PLANT'), str)
    if not plant_id:
        pop_logger.error("Missing PLANT ID in row.")
        return None, None, None, None # Plant is essential for hierarchy
    plant_labels = [plant_id]
    plant_ind = get_or_create_individual(cls_Plant, plant_id, context.onto, add_labels=plant_labels)
    if plant_ind:
        context.set_prop(plant_ind, "plantId", plant_id)
    else: return None, None, None, None # Failed to create plant

    # Area
    area_id = safe_cast(row.get('GH_FOCUSFACTORY'), str) or "UnknownArea"
    area_unique_base = f"{plant_id}_{area_id}"
    area_labels = [area_id]
    area_ind = get_or_create_individual(cls_Area, area_unique_base, context.onto, add_labels=area_labels)
    if area_ind:
        context.set_prop(area_ind, "areaId", area_id)
        context.set_prop(area_ind, "locatedInPlant", plant_ind) # Object Property

    # ProcessCell
    pcell_id = safe_cast(row.get('PHYSICAL_AREA'), str) or "UnknownProcessCell"
    pcell_unique_base = f"{area_unique_base}_{pcell_id}"
    pcell_labels = [pcell_id]
    pcell_ind = get_or_create_individual(cls_ProcessCell, pcell_unique_base, context.onto, add_labels=pcell_labels)
    if pcell_ind:
        context.set_prop(pcell_ind, "processCellId", pcell_id)
        if area_ind: # Link only if Area exists
             context.set_prop(pcell_ind, "partOfArea", area_ind) # Object Property

    # ProductionLine
    line_id = safe_cast(row.get('LINE_NAME'), str)
    if not line_id:
         pop_logger.error("Missing LINE_NAME in row.")
         # Allow continuing without line, but equipment/events might not link correctly later
         line_ind = None
    else:
        line_unique_base = f"{pcell_unique_base}_{line_id}"
        line_labels = [line_id]
        line_ind = get_or_create_individual(cls_ProductionLine, line_unique_base, context.onto, add_labels=line_labels)
        if line_ind:
            context.set_prop(line_ind, "lineId", line_id)
            if pcell_ind: # Link only if ProcessCell exists
                context.set_prop(line_ind, "locatedInProcessCell", pcell_ind) # Object Property

    return plant_ind, area_ind, pcell_ind, line_ind


def process_equipment(row: Dict[str, Any], context: PopulationContext, line_ind: Optional[Thing]) -> Tuple[Optional[Thing], Optional[Thing], Optional[str]]:
    """Processes Equipment and its associated EquipmentClass from a row."""
    cls_Equipment = context.get_class("Equipment")
    cls_EquipmentClass = context.get_class("EquipmentClass")
    if not cls_Equipment or not cls_EquipmentClass: return None, None, None

    eq_id_str = safe_cast(row.get('EQUIPMENT_ID'), str)
    if not eq_id_str:
        pop_logger.debug("No EQUIPMENT_ID in row, skipping equipment creation.")
        return None, None, None

    eq_name = safe_cast(row.get('EQUIPMENT_NAME'), str)
    eq_unique_base = eq_id_str # Assume equipment ID is unique enough
    eq_labels = [f"ID:{eq_id_str}"]
    if eq_name: eq_labels.insert(0, eq_name)

    equipment_ind = get_or_create_individual(cls_Equipment, eq_unique_base, context.onto, add_labels=eq_labels)
    if not equipment_ind:
        pop_logger.error(f"Failed to create Equipment individual for ID '{eq_id_str}'.")
        return None, None, None # Cannot proceed without equipment individual

    # --- Set Equipment Properties ---
    context.set_prop(equipment_ind, "equipmentId", eq_id_str)
    if eq_name: context.set_prop(equipment_ind, "equipmentName", eq_name)
    context.set_prop(equipment_ind, "equipmentModel", safe_cast(row.get('EQUIPMENT_MODEL'), str))
    context.set_prop(equipment_ind, "complexity", safe_cast(row.get('COMPLEXITY'), str))
    context.set_prop(equipment_ind, "alternativeModel", safe_cast(row.get('MODEL'), str))

    # Link Equipment to ProductionLine
    if line_ind:
        context.set_prop(equipment_ind, "isPartOfProductionLine", line_ind)
    else:
         pop_logger.warning(f"Equipment {equipment_ind.name} cannot be linked to line: ProductionLine individual missing.")


    # --- Process and Link EquipmentClass ---
    eq_class_name = parse_equipment_class(eq_name)
    eq_class_ind: Optional[Thing] = None
    if eq_class_name:
        pop_logger.debug(f"Attempting to get/create EquipmentClass: {eq_class_name}")
        eq_class_labels = [eq_class_name]
        eq_class_ind = get_or_create_individual(cls_EquipmentClass, eq_class_name, context.onto, add_labels=eq_class_labels)

        if eq_class_ind:
            pop_logger.debug(f"Successfully got/created EquipmentClass individual: {eq_class_ind.name}")
            # Assign equipmentClassId (Functional)
            context.set_prop(eq_class_ind, "equipmentClassId", eq_class_name)

            # Link Equipment to EquipmentClass (Functional)
            context.set_prop(equipment_ind, "memberOfClass", eq_class_ind)

            # Set default sequence position on the class individual (Functional)
            default_pos = DEFAULT_EQUIPMENT_SEQUENCE.get(eq_class_name)
            if default_pos is not None:
                 # Only set if not already set or different
                 context.set_prop(eq_class_ind, "defaultSequencePosition", default_pos)
            else:
                 # If no default, ensure any existing position is captured for later use
                 existing_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
                 if existing_pos is not None:
                    # We don't need to set it again, but it's good it exists.
                    # The main population function will collect this later.
                    pass
                 else:
                     pop_logger.debug(f"No default sequence position found for class '{eq_class_name}'.")

        else:
            pop_logger.error(f"Failed to get/create EquipmentClass '{eq_class_name}' for Equipment '{equipment_ind.name}'.")
    else:
         pop_logger.warning(f"Could not parse EquipmentClass name from EQUIPMENT_NAME '{eq_name}' for Equipment '{equipment_ind.name}'.")

    return equipment_ind, eq_class_ind, eq_class_name


def process_material(row: Dict[str, Any], context: PopulationContext) -> Optional[Thing]:
    """Processes Material from a row."""
    cls_Material = context.get_class("Material")
    if not cls_Material: return None

    mat_id = safe_cast(row.get('MATERIAL_ID'), str)
    if not mat_id:
        pop_logger.debug("No MATERIAL_ID in row, skipping material creation.")
        return None

    mat_desc = safe_cast(row.get('SHORT_MATERIAL_ID'), str)
    mat_labels = [mat_id]
    if mat_desc: mat_labels.append(mat_desc)

    mat_ind = get_or_create_individual(cls_Material, mat_id, context.onto, add_labels=mat_labels)
    if not mat_ind: return None

    # Set Material properties
    context.set_prop(mat_ind, "materialId", mat_id)
    if mat_desc: context.set_prop(mat_ind, "materialDescription", mat_desc)
    context.set_prop(mat_ind, "sizeType", safe_cast(row.get('SIZE_TYPE'), str))
    context.set_prop(mat_ind, "materialUOM", safe_cast(row.get('MATERIAL_UOM'), str))
    # Combine UOM_ST and UOM_ST_SAP safely
    uom_st = safe_cast(row.get('UOM_ST'), str) or safe_cast(row.get('UOM_ST_SAP'), str)
    context.set_prop(mat_ind, "standardUOM", uom_st)
    context.set_prop(mat_ind, "targetProductUOM", safe_cast(row.get('TP_UOM'), str))
    context.set_prop(mat_ind, "conversionFactor", safe_cast(row.get('PRIMARY_CONV_FACTOR'), float))

    return mat_ind


def process_production_request(row: Dict[str, Any], context: PopulationContext, material_ind: Optional[Thing]) -> Optional[Thing]:
    """Processes ProductionRequest from a row."""
    cls_ProductionRequest = context.get_class("ProductionRequest")
    if not cls_ProductionRequest: return None

    req_id = safe_cast(row.get('PRODUCTION_ORDER_ID'), str)
    if not req_id:
        pop_logger.debug("No PRODUCTION_ORDER_ID in row, skipping production request creation.")
        return None

    req_desc = safe_cast(row.get('PRODUCTION_ORDER_DESC'), str)
    req_labels = [f"ID:{req_id}"]
    if req_desc: req_labels.insert(0, req_desc)

    req_ind = get_or_create_individual(cls_ProductionRequest, req_id, context.onto, add_labels=req_labels)
    if not req_ind: return None

    # Set ProductionRequest properties
    context.set_prop(req_ind, "requestId", req_id)
    if req_desc: context.set_prop(req_ind, "requestDescription", req_desc)
    context.set_prop(req_ind, "requestRate", safe_cast(row.get('PRODUCTION_ORDER_RATE'), float))
    context.set_prop(req_ind, "requestRateUOM", safe_cast(row.get('PRODUCTION_ORDER_UOM'), str))

    # Link ProductionRequest to Material (Non-functional)
    if material_ind:
        context.set_prop(req_ind, "usesMaterial", material_ind)

    return req_ind


def process_shift(row: Dict[str, Any], context: PopulationContext) -> Optional[Thing]:
    """Processes Shift from a row."""
    cls_Shift = context.get_class("Shift")
    if not cls_Shift: return None

    shift_name = safe_cast(row.get('SHIFT_NAME'), str)
    if not shift_name:
        pop_logger.debug("No SHIFT_NAME in row, skipping shift creation.")
        return None

    shift_labels = [shift_name]
    shift_ind = get_or_create_individual(cls_Shift, shift_name, context.onto, add_labels=shift_labels)
    if not shift_ind: return None

    # Populate shift details (Functional properties, assign only if needed/missing)
    # Check before setting to avoid redundant operations if individual already exists
    if getattr(shift_ind, "shiftId", None) != shift_name:
        context.set_prop(shift_ind, "shiftId", shift_name)
    if getattr(shift_ind, "shiftStartTime", None) is None:
         st = safe_cast(row.get('SHIFT_START_DATE_LOC'), datetime)
         if st: context.set_prop(shift_ind, "shiftStartTime", st)
    if getattr(shift_ind, "shiftEndTime", None) is None:
         et = safe_cast(row.get('SHIFT_END_DATE_LOC'), datetime)
         if et: context.set_prop(shift_ind, "shiftEndTime", et)
    if getattr(shift_ind, "shiftDurationMinutes", None) is None:
         dur = safe_cast(row.get('SHIFT_DURATION_MIN'), float)
         if dur is not None: context.set_prop(shift_ind, "shiftDurationMinutes", dur)

    return shift_ind


def process_state_reason(row: Dict[str, Any], context: PopulationContext) -> Tuple[Optional[Thing], Optional[Thing]]:
    """Processes OperationalState and OperationalReason from a row."""
    cls_OperationalState = context.get_class("OperationalState")
    cls_OperationalReason = context.get_class("OperationalReason")
    if not cls_OperationalState or not cls_OperationalReason: return None, None

    # OperationalState
    state_desc = safe_cast(row.get('UTIL_STATE_DESCRIPTION'), str)
    state_ind: Optional[Thing] = None
    if state_desc:
        state_labels = [state_desc]
        state_ind = get_or_create_individual(cls_OperationalState, state_desc, context.onto, add_labels=state_labels)
        if state_ind:
            # Set description (Non-functional)
            context.set_prop(state_ind, "stateDescription", state_desc)
    else:
         pop_logger.debug("No UTIL_STATE_DESCRIPTION in row.")

    # OperationalReason
    reason_desc = safe_cast(row.get('UTIL_REASON_DESCRIPTION'), str)
    reason_ind: Optional[Thing] = None
    if reason_desc:
        reason_labels = [reason_desc]
        reason_ind = get_or_create_individual(cls_OperationalReason, reason_desc, context.onto, add_labels=reason_labels)
        if reason_ind:
            # Set description (Non-functional)
            context.set_prop(reason_ind, "reasonDescription", reason_desc)

            # Handle AltReasonDescription with language tag (Non-functional)
            alt_reason = safe_cast(row.get('UTIL_ALT_LANGUAGE_REASON'), str)
            if alt_reason:
                plant_country = safe_cast(row.get('PLANT_COUNTRY_DESCRIPTION'), str)
                lang_tag = COUNTRY_TO_LANGUAGE.get(plant_country, DEFAULT_LANGUAGE) if plant_country else DEFAULT_LANGUAGE
                try:
                    alt_reason_locstr = locstr(alt_reason, lang=lang_tag)
                    context.set_prop(reason_ind, "altReasonDescription", alt_reason_locstr)
                    pop_logger.debug(f"Added localized reason '{alt_reason}'@{lang_tag} to {reason_ind.name}")
                except Exception as e_loc:
                    pop_logger.warning(f"Failed to create locstr for alt reason '{alt_reason}': {e_loc}. Storing as plain string.")
                    # Fallback to plain string if locstr fails or lang_tag is missing
                    context.set_prop(reason_ind, "altReasonDescription", alt_reason)

            # Other reason properties (Non-functional)
            context.set_prop(reason_ind, "downtimeDriver", safe_cast(row.get('DOWNTIME_DRIVER'), str))
            co_type = safe_cast(row.get('CO_TYPE'), str) or safe_cast(row.get('CO_ORIGINAL_TYPE'), str)
            context.set_prop(reason_ind, "changeoverType", co_type)
    else:
         pop_logger.debug("No UTIL_REASON_DESCRIPTION in row.")

    return state_ind, reason_ind


def process_time_interval(row: Dict[str, Any], context: PopulationContext, resource_base_id: str, row_num: int) -> Optional[Thing]:
    """Processes TimeInterval from a row."""
    cls_TimeInterval = context.get_class("TimeInterval")
    if not cls_TimeInterval: return None

    start_time = safe_cast(row.get('JOB_START_TIME_LOC'), datetime)
    end_time = safe_cast(row.get('JOB_END_TIME_LOC'), datetime)

    if not start_time:
        pop_logger.warning(f"Row {row_num}: Missing JOB_START_TIME_LOC. Cannot create a unique TimeInterval based on start time. Attempting fallback naming.")
        # Fallback naming strategy - less ideal, relies on uniqueness of other fields for the row
        interval_base = f"Interval_{resource_base_id}_Row{row_num}"
        interval_labels = [f"Interval for {resource_base_id} (Row {row_num})"]
        # Proceed even without start time if necessary for the EventRecord
    else:
        # Create a unique TimeInterval using resource, start time, and row number
        start_time_str = start_time.strftime('%Y%m%dT%H%M%S%f')[:-3] # Milliseconds precision
        interval_base = f"Interval_{resource_base_id}_{start_time_str}_{row_num}"
        interval_labels = [f"Interval for {resource_base_id} starting {start_time}"]

    time_interval_ind = get_or_create_individual(cls_TimeInterval, interval_base, context.onto, add_labels=interval_labels)
    if not time_interval_ind:
        pop_logger.error(f"Row {row_num}: Failed to create TimeInterval individual '{interval_base}'.")
        return None

    # Set TimeInterval properties (Functional)
    if start_time: context.set_prop(time_interval_ind, "startTime", start_time)
    if end_time: context.set_prop(time_interval_ind, "endTime", end_time)

    return time_interval_ind


def process_event_record(row: Dict[str, Any], context: PopulationContext,
                         resource_individual: Thing, resource_base_id: str, row_num: int,
                         request_ind: Optional[Thing], material_ind: Optional[Thing],
                         time_interval_ind: Optional[Thing], shift_ind: Optional[Thing],
                         state_ind: Optional[Thing], reason_ind: Optional[Thing]
                        ) -> Optional[Thing]:
    """Processes EventRecord and its links from a row."""
    cls_EventRecord = context.get_class("EventRecord")
    if not cls_EventRecord: return None

    start_time_for_label = getattr(time_interval_ind, "startTime", None) if time_interval_ind else "unknown_time"
    # Use interval base name if available, otherwise construct fallback
    interval_base_name = time_interval_ind.name if time_interval_ind else f"Interval_Row{row_num}_{resource_base_id}"
    event_record_base = f"Event_{interval_base_name}"
    event_labels = [f"Event for {resource_base_id} at {start_time_for_label}"]

    event_ind = get_or_create_individual(cls_EventRecord, event_record_base, context.onto, add_labels=event_labels)
    if not event_ind:
        pop_logger.error(f"Row {row_num}: Failed to create EventRecord individual '{event_record_base}'.")
        return None

    # --- Populate EventRecord Data Properties ---
    context.set_prop(event_ind, "operationType", safe_cast(row.get('OPERA_TYPE'), str))
    context.set_prop(event_ind, "rampUpFlag", safe_cast(row.get('RAMPUP_FLAG'), bool, default=False))
    context.set_prop(event_ind, "reportedDurationMinutes", safe_cast(row.get('TOTAL_TIME'), float))

    # Time Metrics (Functional)
    time_metric_cols = {
        "businessExternalTimeMinutes": "BUSINESS_EXTERNAL_TIME",
        "plantAvailableTimeMinutes": "PLANT_AVAILABLE_TIME",
        "effectiveRuntimeMinutes": "EFFECTIVE_RUNTIME",
        "plantDecisionTimeMinutes": "PLANT_DECISION_TIME",
        "productionAvailableTimeMinutes": "PRODUCTION_AVAILABLE_TIME"
    }
    for prop_name, col_name in time_metric_cols.items():
        val = safe_cast(row.get(col_name), float)
        if val is not None: # Only set if value is valid
            context.set_prop(event_ind, prop_name, val)

    # --- Link EventRecord to other Individuals (Object Properties) ---
    # Link to resource (Line or Equipment) - involvesResource (Non-functional)
    context.set_prop(event_ind, "involvesResource", resource_individual)

    # Link to ProductionRequest (Non-functional)
    if request_ind: context.set_prop(event_ind, "associatedWithProductionRequest", request_ind)

    # Link to Material (Non-functional)
    if material_ind: context.set_prop(event_ind, "usesMaterial", material_ind)

    # Link to TimeInterval (Functional)
    if time_interval_ind: context.set_prop(event_ind, "occursDuring", time_interval_ind)

    # Link to Shift (Functional)
    if shift_ind: context.set_prop(event_ind, "duringShift", shift_ind)

    # Link to OperationalState (Functional)
    if state_ind: context.set_prop(event_ind, "eventHasState", state_ind)

    # Link to OperationalReason (Functional)
    if reason_ind: context.set_prop(event_ind, "eventHasReason", reason_ind)

    # Add links to Personnel, ProcessSegment etc. if data/properties exist

    return event_ind


# --- Main Population Function (Refactored) ---

def populate_ontology_from_data(onto: Ontology,
                                data_rows: List[Dict[str, Any]],
                                defined_classes: Dict[str, ThingClass],
                                defined_properties: Dict[str, PropertyClass],
                                property_is_functional: Dict[str, bool],
                                specification: List[Dict[str, str]] # Pass spec for checks if needed
                               ) -> Tuple[int, Dict[str, Thing], Dict[str, int]]:
    """
    Populates the ontology with individuals and relations from data rows using modular processing functions.

    Returns:
        tuple: (failed_rows_count, created_equipment_class_inds, equipment_class_positions)
            - failed_rows_count: Number of rows that failed processing.
            - created_equipment_class_inds: Maps equipment class name (str) to its individual object.
            - equipment_class_positions: Maps equipment class name (str) to its default sequence position (int).
    """
    pop_logger.info(f"Starting ontology population with {len(data_rows)} data rows.")

    # --- Prepare Context and Check Essentials ---
    context = PopulationContext(onto, defined_classes, defined_properties, property_is_functional)

    # Check essential classes needed by the processing functions
    essential_classes_names = [
        "Plant", "Area", "ProcessCell", "ProductionLine", "Equipment",
        "EquipmentClass", "Material", "ProductionRequest", "EventRecord",
        "TimeInterval", "Shift", "OperationalState", "OperationalReason"
    ]
    missing_classes = [name for name in essential_classes_names if not context.get_class(name)]
    if missing_classes:
        # get_class already logged errors, just return failure
        return len(data_rows), {}, {}

    # Check essential properties needed by the processing functions or sequencing
    essential_prop_names: Set[str] = {
        "plantId", "areaId", "processCellId", "lineId", "equipmentId", "equipmentName",
        "locatedInPlant", "partOfArea", "locatedInProcessCell", "isPartOfProductionLine",
        "memberOfClass", "equipmentClassId", "defaultSequencePosition",
        "materialId", "materialDescription", "usesMaterial",
        "requestId", "requestDescription", "associatedWithProductionRequest",
        "shiftId", "shiftStartTime", "shiftEndTime", "shiftDurationMinutes", "duringShift",
        "stateDescription", "eventHasState",
        "reasonDescription", "altReasonDescription", "eventHasReason",
        "startTime", "endTime", "occursDuring",
        "involvesResource", # Core link for EventRecord
        # Properties needed for sequence setup later (checked here for early failure)
        "classIsUpstreamOf", "classIsDownstreamOf",
        "equipmentIsUpstreamOf", "equipmentIsDownstreamOf"
    }
    missing_essential_props = [name for name in essential_prop_names if not context.get_prop(name)]
    if missing_essential_props:
        pop_logger.error(f"Cannot reliably proceed. Missing essential properties definitions: {missing_essential_props}")
        return len(data_rows), {}, {}

    # Warn about other missing properties defined in spec but not found
    all_spec_prop_names = {row.get('Proposed OWL Property','').strip() for row in specification if row.get('Proposed OWL Property')}
    for spec_prop in all_spec_prop_names:
         if spec_prop and not context.get_prop(spec_prop):
             pop_logger.warning(f"Property '{spec_prop}' (from spec) not found in defined_properties. Population using this property will be skipped.")


    # Track equipment class details across rows for sequencing
    created_equipment_class_inds: Dict[str, Thing] = {} # {eq_class_name_str: eq_class_ind_obj}
    equipment_class_positions: Dict[str, int] = {} # {eq_class_name_str: position_int}


    # --- Process Data Rows ---
    successful_rows = 0
    failed_rows = 0
    with onto: # Use the ontology context for creating individuals
        for i, row in enumerate(data_rows):
            row_num = i + 2 # 1-based index + header row = line number in CSV
            pop_logger.debug(f"--- Processing Row {row_num} ---")
            try:
                # 1. Process Asset Hierarchy -> plant, area, pcell, line individuals
                plant_ind, area_ind, pcell_ind, line_ind = process_asset_hierarchy(row, context)
                if not plant_ind: # Plant is essential to continue processing this row meaningfully
                     raise ValueError("Failed to establish Plant individual, cannot proceed with row.")

                # 2. Determine Resource (Line or Equipment) for the Event
                eq_type = safe_cast(row.get('EQUIPMENT_TYPE'), str)
                resource_individual: Optional[Thing] = None
                resource_base_id: Optional[str] = None # For naming related individuals
                equipment_ind: Optional[Thing] = None
                eq_class_ind: Optional[Thing] = None
                eq_class_name: Optional[str] = None

                if eq_type == 'Line' and line_ind:
                    resource_individual = line_ind
                    resource_base_id = line_ind.name # Use unique IRI name
                    pop_logger.debug(f"Row {row_num}: Identified as Line record for: {line_ind.name}")

                elif eq_type == 'Equipment':
                     # Process Equipment -> equipment, eq_class individuals
                     equipment_ind, eq_class_ind, eq_class_name = process_equipment(row, context, line_ind)
                     if equipment_ind:
                         resource_individual = equipment_ind
                         resource_base_id = f"Eq_{equipment_ind.name}" # Prefix for clarity

                         # Track equipment class info if successfully created/retrieved
                         if eq_class_ind and eq_class_name:
                             if eq_class_name not in created_equipment_class_inds:
                                 created_equipment_class_inds[eq_class_name] = eq_class_ind
                             # Update position map if a position is defined for the class
                             pos = getattr(eq_class_ind, "defaultSequencePosition", None)
                             if pos is not None:
                                  # Check if existing stored pos is different (shouldn't happen with functional prop)
                                  if eq_class_name in equipment_class_positions and equipment_class_positions[eq_class_name] != pos:
                                       pop_logger.warning(f"Sequence position conflict for class '{eq_class_name}'. Existing: {equipment_class_positions[eq_class_name]}, New: {pos}. Using new value: {pos}")
                                  equipment_class_positions[eq_class_name] = pos
                                  pop_logger.debug(f"Tracked position {pos} for class '{eq_class_name}'.")

                     else:
                          pop_logger.warning(f"Row {row_num}: Identified as Equipment record, but failed to process Equipment individual. Event linkages might be incomplete.")
                          # Allow continuing, but event will link to nothing specific if eq failed

                else:
                    pop_logger.warning(f"Row {row_num}: Could not determine resource. EQUIPMENT_TYPE='{eq_type}', EQUIPMENT_ID='{row.get('EQUIPMENT_ID')}', LINE_NAME='{row.get('LINE_NAME')}'. Event linkages might be incomplete.")
                    # Continue processing other parts of the row, but linkages will be affected

                # Check if a resource was identified for linking the event
                if not resource_individual:
                     pop_logger.error(f"Row {row_num}: No valid resource (Line or Equipment) individual identified or created. Cannot link event record correctly.")
                     # Decide whether to skip the rest of the row or continue without linking event
                     # raise ValueError("Resource individual missing, cannot proceed with event linking.") # Stricter approach
                     # Let's continue but log the issue clearly. Event won't link to resource.
                     resource_base_id = f"UnknownResource_Row{row_num}" # Fallback for naming interval/event


                # 3. Process Material -> material individual
                material_ind = process_material(row, context)

                # 4. Process Production Request -> request individual
                request_ind = process_production_request(row, context, material_ind)

                # 5. Process Shift -> shift individual
                shift_ind = process_shift(row, context)

                # 6. Process State & Reason -> state, reason individuals
                state_ind, reason_ind = process_state_reason(row, context)

                # 7. Process Time Interval -> interval individual
                # Requires resource_base_id for unique naming
                time_interval_ind = process_time_interval(row, context, resource_base_id, row_num)

                # 8. Process Event Record and Links -> event individual
                if resource_individual: # Only process event if resource exists
                    event_ind = process_event_record(row, context, resource_individual, resource_base_id, row_num,
                                                    request_ind, material_ind, time_interval_ind,
                                                    shift_ind, state_ind, reason_ind)
                    if not event_ind:
                         # Error logged in process_event_record
                         raise ValueError("Failed to create EventRecord individual.")
                else:
                    pop_logger.warning(f"Row {row_num}: Skipping EventRecord creation as no valid resource individual was found.")


                successful_rows += 1

            except Exception as e:
                failed_rows += 1
                pop_logger.error(f"Error processing data row {row_num}: {row if len(str(row)) < 500 else str(row)[:500] + '...'}")
                pop_logger.exception("Exception details:")

    # --- Log Summaries ---
    pop_logger.info("--- Unique Equipment Classes Found/Created ---")
    if created_equipment_class_inds:
        sorted_class_names = sorted(created_equipment_class_inds.keys())
        pop_logger.info(f"Total unique equipment classes: {len(sorted_class_names)}")
        for class_name in sorted_class_names:
            pop_logger.info(f"  • {class_name} (Position: {equipment_class_positions.get(class_name, 'Not Set')})")
    else:
        pop_logger.warning("No EquipmentClass individuals were created or tracked during population!")

    # No need to log positions separately, included above.

    pop_logger.info(f"Ontology population complete. Successfully processed {successful_rows} rows, failed to process {failed_rows} rows.")
    return failed_rows, created_equipment_class_inds, equipment_class_positions


# --- Sequence Relationship Setup Functions ---

def setup_equipment_sequence_relationships(onto: Ontology,
                                           equipment_class_positions: Dict[str, int],
                                           defined_classes: Dict[str, ThingClass],
                                           defined_properties: Dict[str, PropertyClass],
                                           created_equipment_class_inds: Dict[str, Thing]):
    """
    Establish upstream/downstream relationships between equipment *classes* based on sequence positions.
    """
    pop_logger.info("Setting up CLASS-LEVEL equipment sequence relationships based on position...")

    # Get context for properties/classes
    context = PopulationContext(onto, defined_classes, defined_properties, {}) # is_functional map not needed here

    # Get the CLASS-LEVEL properties
    prop_classIsUpstreamOf = context.get_prop("classIsUpstreamOf")
    prop_classIsDownstreamOf = context.get_prop("classIsDownstreamOf") # Optional for inverse

    if not prop_classIsUpstreamOf:
        pop_logger.error("Cannot establish CLASS-LEVEL sequence relationships: 'classIsUpstreamOf' property not defined.")
        return
    if not prop_classIsDownstreamOf:
        pop_logger.warning("'classIsDownstreamOf' inverse property not found. Only forward class relationships will be set.")

    cls_EquipmentClass = context.get_class("EquipmentClass")
    if not cls_EquipmentClass: return # Should have been caught earlier, but safe check

    # Verify domain/range compatibility (optional but good practice)
    if cls_EquipmentClass not in prop_classIsUpstreamOf.domain:
        pop_logger.warning(f"Property 'classIsUpstreamOf' ({prop_classIsUpstreamOf}) does not have EquipmentClass in its domain {prop_classIsUpstreamOf.domain}.")
    if cls_EquipmentClass not in prop_classIsUpstreamOf.range:
         pop_logger.warning(f"Property 'classIsUpstreamOf' ({prop_classIsUpstreamOf}) does not have EquipmentClass in its range {prop_classIsUpstreamOf.range}.")

    if not created_equipment_class_inds:
        pop_logger.warning("No created EquipmentClass individuals provided. Cannot establish class relationships.")
        return
    if not equipment_class_positions:
        pop_logger.warning("Equipment class positions dictionary is empty. Cannot establish class relationships.")
        return

    # Sort classes by their position number
    sorted_classes = sorted(equipment_class_positions.items(), key=lambda item: item[1])

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
                pop_logger.warning(f"Sequence setup: Upstream class individual '{upstream_class_name}' not found in provided dict.")
                continue
            if not downstream_ind:
                pop_logger.warning(f"Sequence setup: Downstream class individual '{downstream_class_name}' not found in provided dict.")
                continue

            pop_logger.debug(f"Evaluating CLASS relationship: {upstream_ind.name} (Pos {up_pos}) -> {downstream_ind.name} (Pos {down_pos})")

            # Set relationships (classIsUpstreamOf is NON-functional per spec)
            try:
                 # Use helper to check if relationship already exists before appending
                 _set_property_value(upstream_ind, prop_classIsUpstreamOf, downstream_ind, is_functional=False)

                 # Explicitly set the inverse relationship if available and needed
                 if prop_classIsDownstreamOf:
                      _set_property_value(downstream_ind, prop_classIsDownstreamOf, upstream_ind, is_functional=False)

                 # Check if the forward relationship was actually added (or already existed)
                 if downstream_ind in getattr(upstream_ind, "classIsUpstreamOf", []):
                     relationships_created += 1 # Count successful links (new or existing is fine)
                     pop_logger.debug(f"Confirmed CLASS relationship: {upstream_class_name} classIsUpstreamOf {downstream_class_name}")

            except Exception as e:
                pop_logger.error(f"Error setting class relationship {upstream_class_name} -> {downstream_class_name}: {e}")

    pop_logger.info(f"Established/verified {relationships_created} CLASS-LEVEL upstream relationships.")

    # Print relationship summary to stdout
    print("\n=== EQUIPMENT CLASS SEQUENCE RELATIONSHIP REPORT ===")
    if relationships_created > 0:
        print(f"Established/verified {relationships_created} upstream relationships between Equipment Classes:")
        # Re-iterate to print the established sequence
        for i in range(len(sorted_classes) - 1):
            upstream_class_name, _ = sorted_classes[i]
            downstream_class_name, _ = sorted_classes[i + 1]
            # Check if both individuals exist to avoid errors if one was missing during linking
            if created_equipment_class_inds.get(upstream_class_name) and created_equipment_class_inds.get(downstream_class_name):
                print(f"  {upstream_class_name} → {downstream_class_name}")
    else:
        print("No class-level sequence relationships were created or verified.")
    print(f"Total classes with positions considered: {len(sorted_classes)}")


def setup_equipment_instance_relationships(onto: Ontology,
                                           defined_classes: Dict[str, ThingClass],
                                           defined_properties: Dict[str, PropertyClass],
                                           property_is_functional: Dict[str, bool], # Needed for context
                                           equipment_class_positions: Dict[str, int]):
    """
    Establish upstream/downstream relationships between equipment *instances* within the same production line.
    
    The refactored approach:
    1. Group equipment instances by production line and equipment class
    2. For each line, sequence equipment classes based on DEFAULT_EQUIPMENT_SEQUENCE
    3. For each class on a line, sort its instances by equipmentId
    4. Chain instances within the same class sequentially
    5. Chain the last instance of one class to the first instance of the next class
    """
    pop_logger.info("Setting up INSTANCE-LEVEL equipment relationships within production lines...")

    # Get context for properties/classes
    context = PopulationContext(onto, defined_classes, defined_properties, property_is_functional)

    # Get the required classes and properties
    cls_Equipment = context.get_class("Equipment")
    cls_ProductionLine = context.get_class("ProductionLine")
    cls_EquipmentClass = context.get_class("EquipmentClass")
    prop_isPartOfProductionLine = context.get_prop("isPartOfProductionLine")
    prop_memberOfClass = context.get_prop("memberOfClass")
    prop_equipmentClassId = context.get_prop("equipmentClassId") # Needed to get class name string
    prop_equipmentId = context.get_prop("equipmentId") # Needed for sorting instances
    prop_equipment_isUpstreamOf = context.get_prop("equipmentIsUpstreamOf")
    prop_equipment_isDownstreamOf = context.get_prop("equipmentIsDownstreamOf") # Optional for inverse

    # Check essentials
    if not all([cls_Equipment, cls_ProductionLine, cls_EquipmentClass,
                prop_isPartOfProductionLine, prop_memberOfClass, prop_equipmentClassId,
                prop_equipmentId, prop_equipment_isUpstreamOf]):
        pop_logger.error("Missing required classes or properties for equipment instance relationships.")
        return

    if not prop_equipment_isDownstreamOf:
        pop_logger.warning("'equipmentIsDownstreamOf' inverse property not found. Only forward instance relationships will be set.")

    if not equipment_class_positions:
        pop_logger.warning("Equipment class positions dictionary is empty. Cannot establish instance relationships.")
        return

    # Sort class names by position
    sorted_class_names_by_pos = [item[0] for item in sorted(equipment_class_positions.items(), key=lambda item: item[1])]

    if len(sorted_class_names_by_pos) < 1:  # Changed from 2 to 1 since we now chain within classes too
        pop_logger.warning("No equipment classes with sequence positions found. Cannot establish instance relationships.")
        return

    # Group equipment instances by line and class name
    pop_logger.debug("Grouping equipment instances by production line and class name...")
    line_equipment_map: Dict[Thing, Dict[str, List[Thing]]] = {} # {line_individual: {class_name_str: [equipment_instances]}}

    # Iterate through all Equipment individuals in the ontology
    for equipment_inst in onto.search(type=cls_Equipment):
        # Get the line(s) this equipment belongs to (Non-functional)
        equipment_lines = getattr(equipment_inst, "isPartOfProductionLine", [])
        if not equipment_lines:
            pop_logger.debug(f"Equipment {equipment_inst.name} is not linked to any ProductionLine. Skipping.")
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

        # Add equipment to the map for each line it belongs to
        for equipment_line in equipment_lines:
             if not isinstance(equipment_line, cls_ProductionLine):
                 pop_logger.warning(f"Equipment {equipment_inst.name} linked to non-ProductionLine '{equipment_line}'. Skipping this link.")
                 continue

             # Add equipment to the map structure
             if equipment_line not in line_equipment_map:
                 line_equipment_map[equipment_line] = {cn: [] for cn in sorted_class_names_by_pos} # Pre-initialize with sequenced classes
             # Ensure the specific class bucket exists (might not if class wasn't in initial sequence list but had a position)
             if class_name_str not in line_equipment_map[equipment_line]:
                 line_equipment_map[equipment_line][class_name_str] = []

             if equipment_inst not in line_equipment_map[equipment_line][class_name_str]:
                 line_equipment_map[equipment_line][class_name_str].append(equipment_inst)
                 pop_logger.debug(f"Mapped Equipment {equipment_inst.name} to Line {equipment_line.name} under Class '{class_name_str}'")

    # Create instance-level relationships within each line
    total_relationships = 0
    line_relationship_counts: Dict[str, int] = {}
    pop_logger.info(f"Found {len(line_equipment_map)} lines with sequenced equipment.")

    def safe_get_equipment_id(equipment: Thing) -> str:
        """Helper to safely get equipmentId or fallback to name for sorting."""
        equipment_id = getattr(equipment, "equipmentId", None)
        if equipment_id:
            return str(equipment_id)
        return equipment.name

    with onto:
        for line_ind, class_equipment_map_on_line in line_equipment_map.items():
            line_id_str = getattr(line_ind, "lineId", line_ind.name)
            line_relationships = 0
            pop_logger.info(f"Processing equipment instance relationships for line: {line_id_str}")
            
            # Track the last instance in the chain to link between classes
            last_instance_in_chain = None
            
            # Process each equipment class in sequence order
            for class_name in sorted_class_names_by_pos:
                equipment_instances = class_equipment_map_on_line.get(class_name, [])
                
                if not equipment_instances:
                    pop_logger.debug(f"No instances of '{class_name}' found on line {line_id_str}. Continuing to next class.")
                    continue  # No instances for this class on this line, but keep last_instance_in_chain
                
                # Sort equipment instances by equipmentId for sequential chaining
                sorted_instances = sorted(equipment_instances, key=safe_get_equipment_id)
                
                # Log the instances being chained
                instance_ids = [safe_get_equipment_id(e) for e in sorted_instances]
                pop_logger.info(f"Chaining {len(sorted_instances)} instances of '{class_name}' on line '{line_id_str}' by equipmentId: {', '.join(instance_ids)}")
                
                # If there's a previous class's last instance, link it to the first instance of this class
                if last_instance_in_chain:
                    try:
                        # Link the last instance of previous class to first instance of current class
                        _set_property_value(last_instance_in_chain, prop_equipment_isUpstreamOf, sorted_instances[0], is_functional=False)
                        
                        # Set the inverse relation if available
                        if prop_equipment_isDownstreamOf:
                            _set_property_value(sorted_instances[0], prop_equipment_isDownstreamOf, last_instance_in_chain, is_functional=False)
                        
                        line_relationships += 1
                        prev_class = getattr(last_instance_in_chain.memberOfClass, "equipmentClassId", "Unknown")
                        pop_logger.info(f"Linked end of '{prev_class}' chain ({safe_get_equipment_id(last_instance_in_chain)}) " +
                                        f"to start of '{class_name}' chain ({safe_get_equipment_id(sorted_instances[0])}) on line '{line_id_str}'")
                    except Exception as e:
                        pop_logger.error(f"Error linking between class chains on line {line_id_str}: {e}")
                
                # Chain instances within this class sequentially
                if len(sorted_instances) > 1:  # Only need to chain if there are multiple instances
                    internal_links = 0
                    for i in range(len(sorted_instances) - 1):
                        try:
                            upstream_eq = sorted_instances[i]
                            downstream_eq = sorted_instances[i + 1]
                            
                            # Create forward relationship
                            _set_property_value(upstream_eq, prop_equipment_isUpstreamOf, downstream_eq, is_functional=False)
                            
                            # Create inverse relationship if property exists
                            if prop_equipment_isDownstreamOf:
                                _set_property_value(downstream_eq, prop_equipment_isDownstreamOf, upstream_eq, is_functional=False)
                            
                            line_relationships += 1
                            internal_links += 1
                            
                            # Debug level for internal chainings as there could be many
                            pop_logger.debug(f"Chained {class_name} instances: {safe_get_equipment_id(upstream_eq)} → {safe_get_equipment_id(downstream_eq)}")
                        except Exception as e:
                            pop_logger.error(f"Error chaining instances within {class_name} on line {line_id_str}: {e}")
                    
                    if internal_links > 0:
                        pop_logger.info(f"Created {internal_links} internal chain links among {class_name} instances on line {line_id_str}")
                
                # Update last_instance_in_chain to the last instance of the current class
                last_instance_in_chain = sorted_instances[-1]
            
            # Record relationships for this line
            if line_relationships > 0:
                line_relationship_counts[line_id_str] = line_relationships
                total_relationships += line_relationships
                pop_logger.info(f"Established/verified {line_relationships} instance relationships for line {line_id_str}.")

    # Print summary report
    print("\n=== EQUIPMENT INSTANCE RELATIONSHIP REPORT ===")
    if total_relationships > 0:
        pop_logger.info(f"Established/verified {total_relationships} equipment instance relationships across {len(line_relationship_counts)} production lines.")
        print(f"Established/verified {total_relationships} equipment instance relationships on {len(line_relationship_counts)} lines:")
        for line_id_str, count in sorted(line_relationship_counts.items()):
            print(f"  Line {line_id_str}: {count} relationships")
        
        # Print info about the chaining approach
        print("\nChaining approach:")
        print("  • Equipment instances of the same class are chained in sequence by their equipmentId")
        print("  • Last instance of each class is linked to first instance of the next class in sequence")
        print("  • Class sequence is determined by the DEFAULT_EQUIPMENT_SEQUENCE dictionary")
    else:
        pop_logger.warning("No equipment instance relationships were created or verified.")
        print("No equipment instance relationships could be established or verified.")
        print("Possible reasons: Equipment not linked to lines/classes, missing sequence positions, or no equipment found on the same line.")


#======================================================================#
#            create_ontology.py Module Code (Main)                     #
#======================================================================#

# ... (Keep the read_data, generate_reasoning_report, main_ontology_generation, and __main__ sections largely as they are) ...
# Note: Update the call to populate_ontology_from_data in main_ontology_generation to include the 'specification' argument.

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
        report_lines.append(f"    Found {len(inconsistent_classes)} inconsistent classes (see details below)")
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
    if not inconsistent_classes and not inferences_made and use_reasoner: # Check use_reasoner flag
        recommendations.append("⚠️ No inferences made - Ontology is consistent but may lack richness or reasoner configuration issue. Consider adding more specific axioms or reviewing reasoner setup.")
        # Don't flag as issue if reasoner wasn't run
        if use_reasoner: has_issues = True
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
        # Add check for essential properties here too? Already done in populate_ontology_from_data

        # 4. Read Operational Data
        data_rows = read_data(data_file_path)

        # 5. Populate Ontology (ABox) - Using the refactored function
        population_successful = True
        failed_rows_count = 0
        created_eq_classes = {}
        eq_class_positions = {}

        if not data_rows:
            main_logger.warning("No data rows read from data file. Ontology will be populated with structure only.")
        else:
            try:
                failed_rows_count, created_eq_classes, eq_class_positions = populate_ontology_from_data(
                    onto, data_rows, defined_classes, defined_properties, property_is_functional, specification # Pass specification here
                )
                if failed_rows_count == len(data_rows) and len(data_rows) > 0:
                    main_logger.error(f"Population failed for all {len(data_rows)} data rows.")
                    population_successful = False
                elif failed_rows_count > 0:
                    main_logger.warning(f"Population completed with {failed_rows_count} out of {len(data_rows)} failed rows.")
                else:
                    main_logger.info(f"Population completed successfully for all {len(data_rows)} rows.")

                # Logs about created classes/positions are now inside populate_ontology_from_data

            except Exception as pop_exc:
                main_logger.error(f"Critical error during population: {pop_exc}", exc_info=True)
                population_successful = False

        # --- Setup Sequence Relationships AFTER population ---
        if population_successful and created_eq_classes and eq_class_positions:
            main_logger.info("Proceeding to setup sequence relationships...")
            try:
                setup_equipment_sequence_relationships(onto, eq_class_positions, defined_classes, defined_properties, created_eq_classes)
                setup_equipment_instance_relationships(onto, defined_classes, defined_properties, property_is_functional, eq_class_positions)
            except Exception as seq_exc:
                main_logger.error(f"Error during sequence relationship setup: {seq_exc}", exc_info=True)
                # Continue, but log error
        elif population_successful:
            main_logger.warning("Skipping sequence relationship setup because no EquipmentClass individuals or positions were generated/tracked during population.")
        else:
             main_logger.warning("Skipping sequence relationship setup due to population failure.")


        # 6. Apply Reasoning (Optional)
        reasoning_successful = True
        if use_reasoner and population_successful:
            main_logger.info("Applying reasoner (ensure HermiT or compatible reasoner is installed)...")
            try:
                # Use the active world (persistent or default)
                active_world = world if world_db_path else default_world
                with onto: # Use ontology context for reasoning
                    pre_stats = {
                        'classes': len(list(onto.classes())), 'object_properties': len(list(onto.object_properties())),
                        'data_properties': len(list(onto.data_properties())), 'individuals': len(list(onto.individuals()))
                    }
                    main_logger.info("Starting reasoning process...")
                    reasoning_start_time = timing.time()
                    # Run reasoner on the specific world containing the ontology
                    sync_reasoner(infer_property_values=True, debug=0)
                    reasoning_end_time = timing.time()
                    main_logger.info(f"Reasoning finished in {reasoning_end_time - reasoning_start_time:.2f} seconds.")

                    # Collect results from the correct world
                    inconsistent = list(active_world.inconsistent_classes())
                    inferred_hierarchy = {}
                    inferred_properties = {}
                    inferred_individuals = {}
                    # Simplified post-reasoning state collection (as before)
                    for cls in onto.classes():
                         current_subclasses = set(cls.subclasses())
                         inferred_subs = [sub.name for sub in current_subclasses if sub != cls and sub != Nothing] # Exclude self and Nothing
                         # Get direct superclasses AFTER reasoning
                         # direct_supers = set(cls.is_a) - {Thing} - set(cls.ancestors(include_self=True)) # Complex, maybe skip for report
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
                         # Check direct types post-reasoning
                         inferred_chars_for_prop = [char_name for char_name, char_class in inferrable_chars.items() if char_class in prop.is_a]
                         if inferred_chars_for_prop: inferred_properties[prop.name] = inferred_chars_for_prop

                    main_logger.info("Collecting simplified individual inferences (post-reasoning state).")
                    for ind in onto.individuals():
                        # Get direct types post-reasoning
                        current_types = [c.name for c in ind.is_a if c is not Thing]
                        current_props = {}
                        # Check all properties for inferred values
                        for prop in list(onto.object_properties()) + list(onto.data_properties()):
                            try:
                                # Use direct property access post-reasoning
                                values = prop[ind] # Gets inferred values
                                if not isinstance(values, list): values = [values] if values is not None else []

                                if values:
                                    formatted_values = []
                                    for v in values:
                                        if isinstance(v, Thing): formatted_values.append(v.name)
                                        elif isinstance(v, locstr): formatted_values.append(f'"{v}"@{v.lang}')
                                        else: formatted_values.append(repr(v))
                                    if formatted_values: current_props[prop.name] = formatted_values
                            except Exception: continue # Ignore props not applicable or errors

                        if current_types or current_props: # Only report if types or properties inferred/present
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
                    # Use the active world (persistent or default)
                    active_world = world if world_db_path else default_world
                    inconsistent = list(active_world.inconsistent_classes())
                    main_logger.error(f"Inconsistent classes detected: {[c.name for c in inconsistent]}")
                except Exception as e_inc: main_logger.error(f"Could not retrieve inconsistent classes: {e_inc}")
            except NameError as ne:
                 if "sync_reasoner" in str(ne): main_logger.error("Reasoning failed: Reasoner (sync_reasoner) function not found. Is owlready2 installed correctly?")
                 else: main_logger.error(f"Unexpected NameError during reasoning: {ne}")
                 reasoning_successful = False
            except Exception as e:
                main_logger.error(f"An error occurred during reasoning: {e}", exc_info=True)
                reasoning_successful = False
        elif use_reasoner and not population_successful:
             main_logger.warning("Skipping reasoning due to population failure.")


        # 7. Save Ontology
        should_save_primary = population_successful and (not use_reasoner or reasoning_successful)
        final_output_path = output_owl_path
        save_attempted = False

        if not should_save_primary:
            main_logger.error("Ontology generation encountered errors (population or reasoning failure/inconsistency). Ontology will NOT be saved to the primary output file.")
            # Construct debug file path
            base, ext = os.path.splitext(output_owl_path)
            debug_output_path = f"{base}_debug{ext}"
            if debug_output_path == output_owl_path: # Avoid overwriting if extension wasn't .owl or similar
                debug_output_path = output_owl_path + "_debug"

            main_logger.info(f"Attempting to save potentially problematic ontology to: {debug_output_path}")
            final_output_path = debug_output_path
            should_save_debug = True # We always try to save the debug file if primary fails
        else:
            should_save_debug = False # No need for debug file

        if should_save_primary or should_save_debug:
            main_logger.info(f"Saving ontology to {final_output_path} in '{save_format}' format...")
            save_attempted = True
            try:
                # Explicitly pass the world if using persistent storage
                if world_db_path:
                     onto.save(file=final_output_path, format=save_format, world=world)
                else:
                     onto.save(file=final_output_path, format=save_format) # Use default world
                main_logger.info("Ontology saved successfully.")
            except Exception as save_err:
                main_logger.error(f"Failed to save ontology to {final_output_path}: {save_err}", exc_info=True)
                # If saving the primary failed, it's a failure. If saving debug failed, it's still a failure overall.
                return False

        # Determine overall success: Population must succeed, and if reasoning ran, it must succeed.
        # Saving must also have been attempted and not failed (implicit check via not returning False above).
        overall_success = population_successful and (not use_reasoner or reasoning_successful)

        return overall_success

    except Exception as e:
        main_logger.exception("A critical error occurred during the overall ontology generation process.")
        return False

    finally:
        # Close the world ONLY if using persistent storage and it was successfully opened
        # if world_db_path and world:
        #     try:
        #         main_logger.info(f"Closing persistent world: {world_db_path}")
        #         world.close()
        #     except Exception as e_close:
        #          main_logger.error(f"Error closing world database: {e_close}")
        # else:
             # For in-memory, destroying the world can sometimes be useful for cleanup in long-running apps,
             # but is often unnecessary in a script like this. Owlready2 manages the default world internally.
             # main_logger.debug("Destroying in-memory world (optional cleanup).")
             # default_world.destroy() # Or world.destroy() if we assigned it earlier

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