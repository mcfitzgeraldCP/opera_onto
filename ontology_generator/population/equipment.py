"""
Equipment population module for the ontology generator.

This module provides functions for processing equipment data.
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
from ontology_generator.config import DEFAULT_EQUIPMENT_SEQUENCE

def parse_equipment_class(equipment_name: Optional[str], equipment_type: Optional[str] = None, 
                      equipment_model: Optional[str] = None, model: Optional[str] = None,
                      complexity: Optional[str] = None) -> Optional[str]:
    """
    Parses the EquipmentClass from equipment name.
    
    Priority logic for determining equipment class:
    1. Parse from EQUIPMENT_NAME if contains underscore (FIPCO009_Filler)
    2. Check if name matches or contains a known class name
    
    Args:
        equipment_name: The equipment name to parse (primary source)
        equipment_type: Used to validate if it's a Line or Equipment
        equipment_model: Ignored (maintained for backwards compatibility)
        model: Ignored (maintained for backwards compatibility)
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
    from ontology_generator.config import DEFAULT_EQUIPMENT_SEQUENCE
    
    # Skip processing immediately if equipment_type is 'Line'
    if equipment_type and equipment_type.lower() == 'line':
        pop_logger.warning(f"'{equipment_name}' is a Line type - not a valid equipment class")
        return None
        
    # Get known equipment class patterns from config for consistency
    # This ensures we're using the same list that's used for sequencing
    known_equipment_classes = list(DEFAULT_EQUIPMENT_SEQUENCE.keys())
    
    # --- Parse from EQUIPMENT_NAME ---
    if equipment_name and isinstance(equipment_name, str):
        # Case 1: Names with underscores (LINE_CLASS format: FIPCO009_Filler)
        if '_' in equipment_name:
            parts = equipment_name.split('_')
            class_part = parts[-1]  # Take the part after the last underscore

            # Try to extract base class name by removing trailing digits
            base_class = re.sub(r'\d+$', '', class_part)

            # Validate the base class name
            if base_class and re.search(r'[a-zA-Z]', base_class):
                # Further validate that this looks like an equipment class and not a line ID
                if not base_class.startswith("FIPCO"):
                    # Check if this matches or is a substring of a known class
                    for known_class in known_equipment_classes:
                        if base_class == known_class or known_class.startswith(base_class):
                            pop_logger.debug(f"Parsed equipment class '{known_class}' from '{equipment_name}'")
                            return known_class
                    
                    # If we get here, we found a valid class name that's not in the known list
                    pop_logger.debug(f"Parsed equipment class '{base_class}' from '{equipment_name}'")
                    return base_class
                else:
                    pop_logger.warning(f"Part after underscore '{base_class}' looks like a line ID, not a valid equipment class")
        
        # Case 2: Direct CLASS or CLASS# format - check against known classes first (exact match or with trailing numbers)
        # Attempt an exact match with known classes (case-insensitive)
        for known_class in known_equipment_classes:
            # Check if the equipment name IS the class name (with optional trailing digits)
            class_pattern = re.compile(f"^{known_class}\\d*$", re.IGNORECASE)
            if class_pattern.match(equipment_name):
                pop_logger.debug(f"Matched equipment name '{equipment_name}' to class '{known_class}'")
                return known_class
            
            # Alternatively check if name starts with known class followed by numbers
            if equipment_name.startswith(known_class):
                # Check if what follows is just digits
                remainder = equipment_name[len(known_class):]
                if not remainder or remainder.isdigit() or remainder[0].isdigit():
                    pop_logger.debug(f"Extracted equipment class '{known_class}' from '{equipment_name}'")
                    return known_class
        
        # Case 3: Check for known class patterns embedded within the name
        # This is a more permissive check, only used if the more specific checks above fail
        for known_class in known_equipment_classes:
            if known_class in equipment_name:
                # Extract the position of the class name
                start_pos = equipment_name.find(known_class)
                end_pos = start_pos + len(known_class)
                
                # Check if the class name is followed by digits
                if end_pos < len(equipment_name) and equipment_name[end_pos].isdigit():
                    # We found a CLASS# pattern
                    pop_logger.debug(f"Found equipment class '{known_class}' with trailing digits in '{equipment_name}'")
                    return known_class
                
                # If no trailing digits, treat as embedded class name
                pop_logger.debug(f"Found equipment class '{known_class}' within '{equipment_name}'")
                return known_class
        
        # Case 4: Generic extraction for unknown class patterns
        # Try to extract a class-like string if it starts with capital letter and has no spaces
        # Only do this if we couldn't find any match with known classes
        words = re.findall(r'[A-Z][a-zA-Z]*', equipment_name)
        if words:
            for word in words:
                # Look for words that might be equipment classes (proper noun-like)
                if len(word) > 3 and word not in ['LINE', 'FIPCO']:
                    base_class = re.sub(r'\d+$', '', word)
                    pop_logger.debug(f"Extracted potential equipment class '{base_class}' from '{equipment_name}'")
                    return base_class
        
        # Log that we couldn't extract a class
        pop_logger.debug(f"Could not extract valid equipment class from EQUIPMENT_NAME '{equipment_name}'")
    
    # If we reach here, no valid equipment class could be extracted
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
    # Get required classes
    cls_Equipment = context.get_class("Equipment")
    cls_EquipmentClass = context.get_class("EquipmentClass")
    
    if not cls_Equipment or not cls_EquipmentClass:
        pop_logger.error("Required classes (Equipment, EquipmentClass) not found in ontology.")
        return None, None, None

    # Initialize result
    eq_class_ind, eq_ind, eq_class_info_out = None, None, None
    
    # Skip if row doesn't have the minimum equipment data
    eq_name = row.get('EQUIPMENT_NAME', '').strip() if 'EQUIPMENT_NAME' in row else None
    if not eq_name:
        return None, None, None
    
    # Check EQUIPMENT_TYPE to determine if we should process equipment or skip
    eq_type = row.get('EQUIPMENT_TYPE', '').strip() if 'EQUIPMENT_TYPE' in row else 'Equipment'
    
    # If this is a Line type entry, don't create Equipment - it's handled by ProductionLine processing
    if eq_type.lower() == 'line':
        pop_logger.debug(f"EQUIPMENT_TYPE is 'Line' for '{eq_name}' - skipping Equipment instance creation.")
        return None, None, None
    
    # Get equipment identifiers - EQUIPMENT_ID is critical for uniquely identifying the equipment instance
    eq_id = row.get('EQUIPMENT_ID', '').strip() if 'EQUIPMENT_ID' in row else None
    if not eq_id:
        pop_logger.warning(f"Missing EQUIPMENT_ID for equipment named '{eq_name}'. Cannot create unique Equipment instance.")
        return None, None, None

    # Get equipment ID mappings if defined, otherwise default to EQUIPMENT_ID
    eq_id_map = property_mappings.get('Equipment', {}).get('data_properties', {}).get('equipmentId')
    eq_id_col = eq_id_map.get('column') if eq_id_map else 'EQUIPMENT_ID'
    eq_id_value = row.get(eq_id_col, eq_id).strip() if eq_id_col in row else eq_id
    
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
            equipment_type=eq_type
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
    
    # Create the EquipmentClass individual using a stable identifier
    try:
        eq_class_ind = get_or_create_individual(
            cls_EquipmentClass, 
            eq_class_base_name, 
            context.onto, 
            all_created_individuals_by_uid, 
            add_labels=eq_class_labels
        )
        
        if not eq_class_ind:
            pop_logger.error(f"Failed to create/retrieve EquipmentClass individual for '{eq_class_base_name}'")
            
        # Ensure the equipmentClassId data property is set with the correct base name
        prop_equipmentClassId = context.get_prop("equipmentClassId")
        if eq_class_ind and prop_equipmentClassId:
            context.set_prop(eq_class_ind, "equipmentClassId", eq_class_base_name)
            pop_logger.debug(f"Explicitly set equipmentClassId='{eq_class_base_name}' on individual {eq_class_ind.name}")
        
    except Exception as e:
        pop_logger.error(f"Error creating EquipmentClass individual for '{eq_class_base_name}': {e}")
        eq_class_ind = None
    
    # --- EQUIPMENT INDIVIDUAL CREATION ---
    
    # Create descriptive labels for Equipment individual
    equipment_labels = []
    
    # Get line information for more descriptive labels
    line_id = None
    if line_ind:
        line_id = getattr(line_ind, "lineId", None)
        if not line_id and hasattr(line_ind, "name"):
            # Extract from name if attribute not set
            line_name = line_ind.name
            if "ProductionLine_" in line_name:
                line_id = line_name.replace("ProductionLine_", "")
    
    # Build the primary descriptive label
    if eq_id_value and eq_class_base_name and line_id:
        equipment_labels.append(f"Equipment {eq_id_value} ({eq_class_base_name}) on Line {line_id}")
    elif eq_id_value and eq_class_base_name:
        equipment_labels.append(f"Equipment {eq_id_value} ({eq_class_base_name})")
    elif eq_id_value:
        equipment_labels.append(f"Equipment {eq_id_value}")
    
    # Add equipment name as secondary label if available and different from ID
    if eq_name and eq_name != eq_id_value:
        equipment_labels.append(eq_name)
    
    # Always append the ID as a label for easy reference
    if eq_id_value not in equipment_labels:
        equipment_labels.append(eq_id_value)

    # Create equipment individual using ID as the base identifier
    # This ensures uniqueness even when multiple equipment of the same class exist
    try:
        eq_ind = get_or_create_individual(
            cls_Equipment, 
            eq_id_value, 
            context.onto, 
            all_created_individuals_by_uid, 
            add_labels=equipment_labels
        )
        
        if not eq_ind:
            pop_logger.error(f"Failed to create/retrieve Equipment individual for '{eq_id_value}'")
            return None, None, None
            
        # Set the equipmentId data property
        prop_equipmentId = context.get_prop("equipmentId")
        if eq_ind and prop_equipmentId:
            context.set_prop(eq_ind, "equipmentId", eq_id_value)
            pop_logger.debug(f"Set equipmentId='{eq_id_value}' on individual {eq_ind.name}")
        
        # Set the equipmentName data property
        prop_equipmentName = context.get_prop("equipmentName")
        if eq_ind and prop_equipmentName and eq_name:
            context.set_prop(eq_ind, "equipmentName", eq_name)
            pop_logger.debug(f"Set equipmentName='{eq_name}' on individual {eq_ind.name}")
        
        # Link Equipment to EquipmentClass via memberOfClass (only in pass 1)
        if pass_num == 1 and eq_ind and eq_class_ind:
            prop_memberOfClass = context.get_prop("memberOfClass")
            if prop_memberOfClass:
                # Set the memberOfClass relationship
                context.set_prop(eq_ind, "memberOfClass", eq_class_ind)
                pop_logger.debug(f"Linked Equipment {eq_ind.name} to EquipmentClass {eq_class_ind.name} via memberOfClass")
            else:
                pop_logger.error(f"Cannot link Equipment to EquipmentClass: memberOfClass property not found")
        
        # Link Equipment to ProductionLine via isPartOfProductionLine (only in pass 1)
        if pass_num == 1 and eq_ind and line_ind:
            prop_isPartOfProductionLine = context.get_prop("isPartOfProductionLine")
            if prop_isPartOfProductionLine:
                context.set_prop(eq_ind, "isPartOfProductionLine", line_ind)
                pop_logger.debug(f"Linked Equipment {eq_ind.name} to ProductionLine {line_ind.name} via isPartOfProductionLine")
                
                # Also set the associatedLineId data property for easy reference
                prop_associatedLineId = context.get_prop("associatedLineId")
                if prop_associatedLineId and line_id:
                    context.set_prop(eq_ind, "associatedLineId", line_id)
                    pop_logger.debug(f"Set associatedLineId='{line_id}' on Equipment {eq_ind.name}")
    
    except Exception as e:
        pop_logger.error(f"Error creating Equipment individual for '{eq_id_value}': {e}")
        eq_ind = None
    
    # Prepare info for tracking - we don't need to track defaultSequencePosition anymore
    if eq_class_base_name and eq_class_ind:
        eq_class_info_out = (eq_class_base_name, eq_class_ind, None)
    else:
        eq_class_info_out = None
    
    return eq_ind, eq_class_ind, eq_class_info_out
