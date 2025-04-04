"""
Equipment population module for the ontology generator.

This module provides functions for processing equipment data.

Equipment Class Identification
-----------------------------
The ontology generator supports multiple strategies for identifying the correct equipment class 
from equipment data. Configuration options are available in config.py:

1. EQUIPMENT_NAME_TO_CLASS_MAP: A dictionary mapping patterns found in equipment names to their 
   corresponding equipment class. This is the highest priority matching method.
   Example: {"_Filler": "Filler", "TFS30": "TubeFillingSealer30"}

2. KNOWN_EQUIPMENT_CLASSES: A list of all known equipment classes used for fallback matching 
   when direct mapping fails.
   
The parse_equipment_class function uses the following priority order:
1. Direct pattern match using EQUIPMENT_NAME_TO_CLASS_MAP
2. Parse from underscore format (e.g., "FIPCO009_Filler" → "Filler")
3. Match against KNOWN_EQUIPMENT_CLASSES (exact match, prefix match, or substring)
4. Equipment model inspection (if available)
5. Generic string extraction (last resort)

When the function identifies a class, it logs which method was used for traceability.
"""
import re
from typing import Dict, Any, Optional, Tuple

from owlready2 import Thing

from ontology_generator.utils.logging import pop_logger
from ontology_generator.utils.types import safe_cast
from ontology_generator.population.core import (
    PopulationContext, get_or_create_individual, 
    apply_data_property_mappings, apply_object_property_mappings
)
from ontology_generator.config import DEFAULT_EQUIPMENT_SEQUENCE, KNOWN_EQUIPMENT_CLASSES, EQUIPMENT_NAME_TO_CLASS_MAP

def parse_equipment_class(equipment_name: Optional[str], equipment_type: Optional[str] = None, 
                      equipment_model: Optional[str] = None, model: Optional[str] = None,
                      complexity: Optional[str] = None) -> Optional[str]:
    """
    Parses the EquipmentClass from equipment name.
    
    Priority logic for determining equipment class:
    1. Check for match in EQUIPMENT_NAME_TO_CLASS_MAP
    2. Parse from EQUIPMENT_NAME if contains underscore (FIPCO009_Filler)
    3. Check if name matches or contains a known class name from KNOWN_EQUIPMENT_CLASSES
    4. Equipment model inspection (if available)
    5. Generic string parsing as fallback
    
    Args:
        equipment_name: The equipment name to parse (primary source)
        equipment_type: Used to validate if it's a Line or Equipment
        equipment_model: Can provide additional clues for equipment class if name is unclear
        model: Alias for equipment_model (maintained for backwards compatibility)
        complexity: Ignored (maintained for backwards compatibility)
        
    Returns:
        The parsed equipment class name or None
    
    Examples:
    - FIPCO009_Filler -> Filler
    - FIPCO009_Filler2 -> Filler (trailing numbers are removed)
    - CasePacker2 -> CasePacker (trailing numbers are removed)
    - FIPCO009_CaseFormer3 -> CaseFormer (trailing numbers are removed)
    - LINE_CLASS (FIPCO009_Filler) -> Filler
    - CLASS (Filler) -> Filler
    - LINE_CLASS# (FIPCO009_Filler2) -> Filler
    - CLASS# (Filler2) -> Filler
    """
    from ontology_generator.config import KNOWN_EQUIPMENT_CLASSES, EQUIPMENT_NAME_TO_CLASS_MAP
    
    # Skip processing immediately if equipment_type is 'Line'
    if equipment_type and equipment_type.lower() == 'line':
        pop_logger.warning(f"'{equipment_name}' is a Line type - not a valid equipment class")
        return None
        
    # Initialize match method tracking (for logging)
    match_method = "None"
    matched_class = None
    
    # --- Process inputs and validate --- 
    if not equipment_name:
        pop_logger.warning("Equipment name is empty or None, cannot parse equipment class")
        return None
        
    # Use equipment_model parameter if provided, otherwise fall back to model parameter
    actual_model = equipment_model if equipment_model else model
    
    # Log equipment name for debugging
    pop_logger.debug(f"Attempting to parse equipment class from: '{equipment_name}'")
    if actual_model:
        pop_logger.debug(f"Equipment model information: '{actual_model}'")
    
    # --- Method 1: Direct match from configuration map ---
    if equipment_name and isinstance(equipment_name, str):
        for pattern, class_name in EQUIPMENT_NAME_TO_CLASS_MAP.items():
            if pattern in equipment_name:
                match_method = "Config Map"
                matched_class = class_name
                pop_logger.info(f"Found equipment class '{matched_class}' via pattern '{pattern}' in config map")
                break
                
    # --- Method 2: Parse from EQUIPMENT_NAME with underscore ---
    if not matched_class and equipment_name and isinstance(equipment_name, str) and '_' in equipment_name:
        # Split on underscore and take part after the last underscore
        parts = equipment_name.split('_')
        class_part = parts[-1].strip()  # Take the part after the last underscore and remove whitespace

        # Try to extract base class name by removing trailing digits
        base_class = re.sub(r'\d+$', '', class_part)
        
        # Clean up any remaining non-alphanumeric characters
        base_class = re.sub(r'[^a-zA-Z0-9]', '', base_class)

        # Validate the base class name
        if base_class and re.search(r'[a-zA-Z]', base_class):
            # Further validate that this looks like an equipment class and not a line ID
            if not re.match(r'^(FIPCO|LINE)\d*$', base_class, re.IGNORECASE):
                # Check if this matches or is a substring of a known class
                match_found = False
                for known_class in KNOWN_EQUIPMENT_CLASSES:
                    if base_class.lower() == known_class.lower():
                        # Exact match (case insensitive)
                        match_method = "Name Underscore Parsing (Exact Match)"
                        matched_class = known_class  # Use the properly capitalized version
                        match_found = True
                        pop_logger.info(f"Parsed equipment class '{matched_class}' via exact match from '{equipment_name}'")
                        break
                    elif known_class.lower().startswith(base_class.lower()):
                        # Known class starts with our parsed base class - likely a match
                        match_method = "Name Underscore Parsing (Prefix Match)"
                        matched_class = known_class
                        match_found = True
                        pop_logger.info(f"Parsed equipment class '{matched_class}' via prefix match from '{equipment_name}'")
                        break
                
                # If we didn't find a match in known classes but have a valid class name
                if not match_found and len(base_class) >= 3:
                    match_method = "Name Underscore Parsing (New Class)"
                    matched_class = base_class
                    pop_logger.info(f"Parsed potential new equipment class '{matched_class}' from '{equipment_name}'")
            else:
                pop_logger.debug(f"Part after underscore '{base_class}' looks like a line ID, not a valid equipment class")
    
    # --- Method 3: Known Class Matching (without underscore) ---
    if not matched_class and equipment_name and isinstance(equipment_name, str):
        # Remove any line ID prefix first (e.g., FIPCO009, LINE1)
        cleaned_name = re.sub(r'^(FIPCO|LINE)\d*_?', '', equipment_name)
        
        # Extract parenthesized content if present - often contains class info
        paren_match = re.search(r'\((.*?)\)', cleaned_name)
        if paren_match:
            paren_content = paren_match.group(1).strip()
            pop_logger.debug(f"Found parenthesized content: '{paren_content}'")
            
            # Try to extract from parenthesized content first (higher priority)
            for known_class in KNOWN_EQUIPMENT_CLASSES:
                if known_class.lower() in paren_content.lower():
                    match_method = "Parenthesized Content Match"
                    matched_class = known_class
                    pop_logger.info(f"Extracted equipment class '{matched_class}' from parenthesized content in '{equipment_name}'")
                    break
        
        if not matched_class:
            # Remove trailing numbers
            base_name = re.sub(r'\d+$', '', cleaned_name)
            pop_logger.debug(f"Cleaned base name for matching: '{base_name}'")
            
            # Clean up any remaining non-alphanumeric characters for better matching
            cleaned_base = re.sub(r'[^a-zA-Z0-9\s]', '', base_name).strip()
            
            # Try various matching strategies with known classes
            for known_class in KNOWN_EQUIPMENT_CLASSES:
                # 1. Exact match with known classes (case-insensitive)
                if cleaned_base.lower() == known_class.lower():
                    match_method = "Known Class Exact Match"
                    matched_class = known_class  # Use the properly capitalized version
                    pop_logger.info(f"Matched equipment name '{equipment_name}' to known class '{matched_class}' (exact match)")
                    break
                
                # 2. Check if cleaned name starts with known class (case-insensitive)
                if cleaned_base.lower().startswith(known_class.lower()):
                    # Ensure what follows isn't alphabetic (could be a longer but different class name)
                    remainder = cleaned_base[len(known_class):].strip()
                    if not remainder or not re.search(r'[a-zA-Z]', remainder):
                        match_method = "Known Class Prefix Match"
                        matched_class = known_class
                        pop_logger.info(f"Extracted equipment class '{matched_class}' from '{equipment_name}' via prefix match")
                        break
                
                # 3. Check if a known class is embedded within the name
                if known_class.lower() in cleaned_base.lower():
                    match_method = "Known Class Substring Match" 
                    matched_class = known_class
                    pop_logger.info(f"Found equipment class '{matched_class}' embedded within '{equipment_name}'")
                    break
                
                # 4. Check for word boundary matches (most precise)
                word_pattern = r'\b' + re.escape(known_class.lower()) + r'\b'
                if re.search(word_pattern, cleaned_base.lower()):
                    match_method = "Known Class Word Match"
                    matched_class = known_class
                    pop_logger.info(f"Found equipment class '{matched_class}' as a complete word in '{equipment_name}'")
                    break
    
    # --- Method 4: Equipment Model Inspection ---
    if not matched_class and actual_model and isinstance(actual_model, str):
        model_to_use = actual_model.strip()
        pop_logger.debug(f"Attempting to parse class from equipment model: '{model_to_use}'")
        
        # Look for known classes in the model information
        for known_class in KNOWN_EQUIPMENT_CLASSES:
            if known_class.lower() in model_to_use.lower():
                match_method = "Model-Based Match"
                matched_class = known_class
                pop_logger.info(f"Extracted equipment class '{matched_class}' from model '{model_to_use}'")
                break
    
    # --- Method 5: Generic String Extraction (most permissive, last resort) ---
    if not matched_class and equipment_name and isinstance(equipment_name, str):
        pop_logger.debug(f"Attempting generic string extraction as last resort for '{equipment_name}'")
        # Remove any line ID prefix first
        cleaned_name = re.sub(r'^(FIPCO|LINE)\d*_?', '', equipment_name)
        
        # Try to extract a class-like string if it has proper capitalization
        words = re.findall(r'[A-Z][a-zA-Z]*', cleaned_name)
        if words:
            candidate_classes = []
            for word in words:
                # Identify potential equipment class names (proper noun-like with meaningful length)
                if len(word) > 3 and word not in ['LINE', 'FIPCO', 'TEST', 'TEMP', 'UNIT']:
                    base_class = re.sub(r'\d+$', '', word)
                    candidate_classes.append((base_class, len(base_class)))
            
            # Sort candidates by length (prefer longer class names as they're typically more specific)
            if candidate_classes:
                # Sort by length in descending order
                sorted_candidates = sorted(candidate_classes, key=lambda x: x[1], reverse=True)
                best_candidate = sorted_candidates[0][0]
                
                # Check if the best candidate is similar to a known class
                similar_to_known = False
                most_similar_known = None
                for known_class in KNOWN_EQUIPMENT_CLASSES:
                    # Simple similarity check - case insensitive starts with
                    if known_class.lower().startswith(best_candidate.lower()) or best_candidate.lower().startswith(known_class.lower()):
                        similar_to_known = True
                        most_similar_known = known_class
                        break
                
                if similar_to_known and most_similar_known:
                    match_method = "Generic Extraction (Similar to Known Class)"
                    matched_class = most_similar_known
                    pop_logger.info(f"Extracted equipment class '{matched_class}' via similarity to extracted candidate '{best_candidate}'")
                else:
                    match_method = "Generic String Extraction"
                    matched_class = best_candidate
                    pop_logger.info(f"Extracted potential equipment class '{matched_class}' via generic parsing from candidates: {[c[0] for c in candidate_classes]}")
    
    # Final validation and logging
    if matched_class:
        # Ensure the matched class has proper capitalization if it's a known class
        for known_class in KNOWN_EQUIPMENT_CLASSES:
            if matched_class.lower() == known_class.lower():
                matched_class = known_class  # Use the properly capitalized version
                break
        
        pop_logger.info(f"Successfully parsed equipment class '{matched_class}' from '{equipment_name}' using method: {match_method}")
        return matched_class
    else:
        # More detailed logging for troubleshooting
        if equipment_type and equipment_type.lower() == 'equipment':
            pop_logger.warning(f"CRITICAL: Could not extract valid equipment class from EQUIPMENT_NAME='{equipment_name}' with type 'Equipment'")
        else:
            pop_logger.warning(f"Could not extract valid equipment class from EQUIPMENT_NAME='{equipment_name}'")
        return None

def process_equipment_and_class(
    row: Dict[str, Any],
    context: PopulationContext,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: Dict[Tuple[str, str], Thing] = None,
    line_ind: Optional[Thing] = None,
    pass_num: int = 1
) -> Tuple[Optional[Thing], Optional[Thing], Optional[Tuple]]:
    """
    Process equipment data to create/retrieve Equipment and EquipmentClass individuals.
    
    Args:
        row: The data row/dict being processed.
        context: The population context with ontology, classes and properties.
        property_mappings: Property mappings dictionary for populating individuals.
        all_created_individuals_by_uid: Registry of created individuals for reuse.
        line_ind: Optional production line individual to link to (if available).
        pass_num: The current processing pass (1 or 2).
    
    Returns:
        Tuple: (equipment_ind, equipment_class_ind, equipment_class_info)
               - equipment_ind: Created/retrieved Equipment individual (or None)
               - equipment_class_ind: Created/retrieved EquipmentClass individual (or None)
               - equipment_class_info: (Optional) Tuple with class name, individual, and sequence info
    """
    # Validate essential inputs
    if not property_mappings:
        pop_logger.warning("Property mappings not provided to process_equipment_and_class. Skipping.")
        return None, None, None
    if all_created_individuals_by_uid is None:
        pop_logger.error("Individual registry not provided to process_equipment_and_class. Skipping.")
        return None, None, None
    
    # Get required classes
    cls_Equipment = context.get_class("Equipment")
    cls_EquipmentClass = context.get_class("EquipmentClass")
    
    if not cls_Equipment or not cls_EquipmentClass:
        pop_logger.error("Required classes (Equipment, EquipmentClass) not found in ontology.")
        return None, None, None

    # Initialize result
    eq_class_ind, eq_ind, eq_class_info_out = None, None, None
    
    # Check for equipment name property - critical for identification
    eq_name = None
    eq_name_map = property_mappings.get('Equipment', {}).get('data_properties', {}).get('equipmentName')
    if eq_name_map and eq_name_map.get('column') and eq_name_map['column'] in row:
        eq_name = row.get(eq_name_map['column'], '').strip()
    else:
        # Fall back to direct column lookup
        eq_name = row.get('EQUIPMENT_NAME', '').strip() if 'EQUIPMENT_NAME' in row else None
    
    if not eq_name:
        pop_logger.warning("Missing equipment name. Cannot create equipment instance.")
        return None, None, None
    
    # Check EQUIPMENT_TYPE to determine if we should process equipment or skip
    eq_type = None
    eq_type_map = property_mappings.get('Equipment', {}).get('data_properties', {}).get('equipmentType')
    if eq_type_map and eq_type_map.get('column') and eq_type_map['column'] in row:
        eq_type = row.get(eq_type_map['column'], '').strip()
    else:
        # Fall back to direct column lookup
        eq_type = row.get('EQUIPMENT_TYPE', '').strip() if 'EQUIPMENT_TYPE' in row else 'Equipment'
    
    # If this is a Line type entry, don't create Equipment - it's handled by ProductionLine processing
    if eq_type.lower() == 'line':
        pop_logger.debug(f"EQUIPMENT_TYPE is 'Line' for '{eq_name}' - skipping Equipment instance creation.")
        return None, None, None
    
    # Get equipment ID - critical for uniquely identifying the equipment instance
    # Check for equipmentId property mapping
    eq_id = None
    eq_id_map = property_mappings.get('Equipment', {}).get('data_properties', {}).get('equipmentId')
    if eq_id_map and eq_id_map.get('column') and eq_id_map['column'] in row:
        eq_id = row.get(eq_id_map['column'], '').strip()
    else:
        # Fall back to direct column lookup
        eq_id = row.get('EQUIPMENT_ID', '').strip() if 'EQUIPMENT_ID' in row else None
    
    if not eq_id:
        pop_logger.warning(f"Missing equipment ID for equipment named '{eq_name}'. Cannot create unique Equipment instance.")
        return None, None, None

    # --- EQUIPMENT CLASS IDENTIFICATION ---
    
    # Create/retrieve equipment class from equipment name/type
    eq_class_id_map = property_mappings.get('EquipmentClass', {}).get('data_properties', {}).get('equipmentClassId')
    eq_class_col = eq_class_id_map.get('column') if eq_class_id_map else None
    eq_class_name_map = property_mappings.get('EquipmentClass', {}).get('data_properties', {}).get('equipmentClassName')
    
    eq_class_base_name = None
    eq_class_labels = []
    is_parsed_from_name = False
    
    # Method 1: Try to get directly from a mapped column for equipmentClassId
    if eq_class_col and eq_class_col in row and row[eq_class_col]:
        eq_class_id_value = row[eq_class_col].strip()
        if eq_class_id_value:
            eq_class_base_name = eq_class_id_value
            pop_logger.debug(f"Using equipment class '{eq_class_base_name}' from column '{eq_class_col}'")
    
    # Method 2: Try to parse from equipment name if not yet determined
    if not eq_class_base_name:
        parsed_class = parse_equipment_class(
            equipment_name=eq_name,
            equipment_type=eq_type,
            equipment_model=row.get('EQUIPMENT_MODEL', '') # Add potential model information
        )
        if parsed_class:
            eq_class_base_name = parsed_class
            eq_class_id_value = parsed_class  # Use parsed value as ID value
            is_parsed_from_name = True
            pop_logger.debug(f"Parsed equipment class '{eq_class_base_name}' from equipment name '{eq_name}'")
    
    # If still no class name, use a default or return None
    if not eq_class_base_name:
        pop_logger.warning(f"Could not determine equipment class for '{eq_name}'. Using 'GenericEquipment' as fallback.")
        eq_class_base_name = "GenericEquipment"
        eq_class_id_value = "GenericEquipment"  # Use generic value
    
    # Set proper label for equipment class - use the parsed/determined type name
    # This is the primary label for EquipmentClass
    eq_class_labels = [eq_class_base_name]
    
    # Optionally add the original EQUIPMENT_NAME as a supplementary label if we parsed
    if is_parsed_from_name and eq_class_id_value and eq_class_id_value != eq_class_base_name:
        eq_class_labels.append(f"Source Name: {eq_class_id_value}")
    
    # --- EQUIPMENT CLASS INDIVIDUAL CREATION ---
    
    # CRITICAL FIX: Use the class base name as the unique identifier
    # This ensures only one EquipmentClass individual per type (e.g., one :Filler)
    try:
        # Key modification for TKT-001: Use eq_class_base_name directly as unique ID 
        # rather than using the full equipment name
        eq_class_unique_id = eq_class_base_name
        
        pop_logger.debug(f"Creating/retrieving EquipmentClass individual with unique ID: '{eq_class_unique_id}'")
        
        eq_class_ind = get_or_create_individual(
            cls_EquipmentClass, 
            eq_class_unique_id, 
            context.onto, 
            all_created_individuals_by_uid, 
            add_labels=eq_class_labels
        )
        
        # Set the sequence position property during population, if available
        eq_class_sequence_map = property_mappings.get('EquipmentClass', {}).get('data_properties', {}).get('classSequencePosition')
        if eq_class_ind and pass_num == 1:
            # Check if the sequence is from the DEFAULT_EQUIPMENT_SEQUENCE or from a column
            sequence_position = None
            
            # Try to get from config first
            if eq_class_base_name in KNOWN_EQUIPMENT_CLASSES:
                sequence_position = KNOWN_EQUIPMENT_CLASSES.index(eq_class_base_name) + 1
                pop_logger.debug(f"Retrieved sequence position {sequence_position} for {eq_class_base_name} from KNOWN_EQUIPMENT_CLASSES")
            
            # TKT-005: Explicitly set equipmentClassId to ensure it matches the base name
            # This ensures the EquipmentClass can be properly identified and linked
            pop_logger.info(f"TKT-005: Setting equipmentClassId='{eq_class_base_name}' for EquipmentClass individual '{eq_class_unique_id}'")
            context.set_prop(eq_class_ind, "equipmentClassId", eq_class_base_name)
            
            # Apply data property mappings for EquipmentClass
            if "EquipmentClass" in property_mappings:
                apply_data_property_mappings(eq_class_ind, property_mappings["EquipmentClass"], row, context, "EquipmentClass", pop_logger)
            
            # Create tuple with equipment class info for return
            eq_class_info_out = (eq_class_base_name, eq_class_ind, sequence_position)
    except Exception as e:
        pop_logger.error(f"Error creating EquipmentClass '{eq_class_base_name}': {e}")
        # Return meaningful error details
        if not eq_class_base_name:
            pop_logger.error("Failed due to missing class base name")
        elif not cls_EquipmentClass:
            pop_logger.error("Failed due to missing EquipmentClass class in ontology")
    
    # --- EQUIPMENT INDIVIDUAL CREATION ---
    
    # CRITICAL FIX: Ensure we use the equipment ID as the unique identifier
    if eq_id:
        # Create descriptive labels for Equipment
        eq_labels = []
        
        # Primary label: Full equipment name if available (most descriptive)
        eq_labels.append(eq_name)
        
        # Ensure equipment ID is in labels if not the same as name
        if eq_id != eq_name:
            eq_labels.append(f"ID: {eq_id}")
        
        # Add class information if available
        if eq_class_base_name:
            eq_labels.append(f"Type: {eq_class_base_name}")
            
        # Create the Equipment individual using equipment ID as the unique identifier
        try:
            # Key modification for TKT-002-2c: Explicitly use EQUIPMENT_ID for unique identification
            eq_unique_id = eq_id
            
            pop_logger.debug(f"Creating/retrieving Equipment individual with unique ID: '{eq_unique_id}'")
            
            eq_ind = get_or_create_individual(
                cls_Equipment,
                eq_unique_id,  # Use equipment ID as base for stable identifier
                context.onto,
                all_created_individuals_by_uid,
                add_labels=eq_labels
            )
            
            if eq_ind and pass_num == 1:
                # Apply data properties for Equipment
                if "Equipment" in property_mappings:
                    apply_data_property_mappings(eq_ind, property_mappings["Equipment"], row, context, "Equipment", pop_logger)
                
                # --- TKT-005: EXPLICIT EQUIPMENT TO CLASS LINKING ---
                
                # Ensure memberOfClass relationship is established between Equipment and EquipmentClass
                if eq_ind and eq_class_ind:
                    # Check if the memberOfClass property is available before attempting to set it
                    member_of_class_prop = context.get_prop("memberOfClass")
                    if member_of_class_prop:
                        # Set the memberOfClass relationship
                        context.set_prop(eq_ind, "memberOfClass", eq_class_ind)
                        pop_logger.info(f"TKT-005: Linked equipment '{eq_id}' to its class '{eq_class_base_name}' via memberOfClass property")
                    else:
                        pop_logger.error(f"CRITICAL: Required property 'memberOfClass' not found. Cannot link equipment to class.")
                elif not eq_class_ind:
                    pop_logger.error(f"CRITICAL: Failed to establish memberOfClass link - missing class individual for '{eq_class_base_name}'")
                
                # TKT-002: Set sequencePosition property on the Equipment individual based on its class
                # First check if the sequencePosition property exists
                sequence_position_prop = context.get_prop("sequencePosition")
                if sequence_position_prop:
                    # Determine sequence position from equipment class
                    position_value = None
                    
                    # Try to get line ID for line-specific sequence positions
                    line_id = None
                    if line_ind:
                        line_id_prop = context.get_prop("lineId")
                        if line_id_prop:
                            line_id = getattr(line_ind, line_id_prop.python_name, None)
                    
                    # TKT-006: Enhanced logic for finding sequence position based on equipment class
                    if eq_class_base_name:
                        # First check if there's a line-specific sequence
                        from ontology_generator.config import LINE_SPECIFIC_EQUIPMENT_SEQUENCE
                        if line_id and line_id in LINE_SPECIFIC_EQUIPMENT_SEQUENCE and eq_class_base_name in LINE_SPECIFIC_EQUIPMENT_SEQUENCE[line_id]:
                            position_value = LINE_SPECIFIC_EQUIPMENT_SEQUENCE[line_id].get(eq_class_base_name)
                            pop_logger.debug(f"Using line-specific sequence position {position_value} for {eq_class_base_name} on line {line_id}")
                        
                        # Otherwise, use the default sequence from DEFAULT_EQUIPMENT_SEQUENCE
                        if position_value is None:
                            from ontology_generator.config import DEFAULT_EQUIPMENT_SEQUENCE
                            position_value = DEFAULT_EQUIPMENT_SEQUENCE.get(eq_class_base_name)
                            if position_value:
                                pop_logger.debug(f"Using default sequence position {position_value} for {eq_class_base_name}")
                    
                    # Set the sequencePosition if we found a value
                    if position_value is not None:
                        context.set_prop(eq_ind, "sequencePosition", position_value)
                        pop_logger.debug(f"TKT-006: Set sequencePosition={position_value} for equipment {eq_id} of class {eq_class_base_name}")
                    else:
                        pop_logger.warning(f"TKT-006: No sequence position found for equipment class {eq_class_base_name}")
                else:
                    pop_logger.warning(f"Required property 'sequencePosition' not found. Cannot set sequence position.")
                
                # 2. Link equipment to its production line if available
                if eq_ind and line_ind:
                    # Check for existence of isPartOfProductionLine property before attempting to set it
                    part_of_line_prop = context.get_prop("isPartOfProductionLine")
                    if part_of_line_prop:
                        # Set bidirectional links
                        context.set_prop(eq_ind, "isPartOfProductionLine", line_ind)
                        
                        # Check for existence of hasEquipmentPart property before attempting to set it
                        has_part_prop = context.get_prop("hasEquipmentPart")
                        if has_part_prop:
                            context.set_prop(line_ind, "hasEquipmentPart", eq_ind)
                            pop_logger.debug(f"Linked equipment '{eq_name}' to production line")
                        else:
                            pop_logger.warning(f"Required property mapping 'hasEquipmentPart' not found. Cannot link line to equipment.")
                    else:
                        pop_logger.warning(f"Required property mapping 'isPartOfProductionLine' not found. Cannot link equipment to line.")
                    
        except Exception as e:
            pop_logger.error(f"Error creating Equipment '{eq_id}': {e}")
    
    return eq_ind, eq_class_ind, eq_class_info_out

def process_equipment(
    row: Dict[str, Any],
    context: PopulationContext,
    line_ind: Optional[Thing] = None,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
) -> Tuple[Optional[Thing], Optional[Thing], Optional[str]]:
    """
    Process equipment data to create/retrieve Equipment and EquipmentClass individuals.
    
    This is a wrapper around process_equipment_and_class to maintain backward compatibility.
    
    Args:
        row: The data row/dict being processed.
        context: The population context with ontology, classes and properties.
        line_ind: Optional production line individual to link to (if available).
        property_mappings: Property mappings dictionary for populating individuals.
    
    Returns:
        Tuple: (equipment_ind, equipment_class_ind, equipment_class_name)
               - equipment_ind: Created/retrieved Equipment individual (or None)
               - equipment_class_ind: Created/retrieved EquipmentClass individual (or None)
               - equipment_class_name: Name of the equipment class (or None)
    """
    all_created_individuals_by_uid = {}  # Create empty registry for the single call
    
    eq_ind, eq_class_ind, eq_class_info = process_equipment_and_class(
        row=row,
        context=context,
        property_mappings=property_mappings,
        all_created_individuals_by_uid=all_created_individuals_by_uid,
        line_ind=line_ind,
        pass_num=1
    )
    
    # Extract the class name from the tuple if available
    eq_class_name = eq_class_info[0] if eq_class_info and len(eq_class_info) > 0 else None
    
    return eq_ind, eq_class_ind, eq_class_name
