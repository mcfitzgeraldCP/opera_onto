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
    """
    # Skip processing immediately if equipment_type is 'Line'
    if equipment_type and equipment_type.lower() == 'line':
        pop_logger.warning(f"'{equipment_name}' is a Line type - not a valid equipment class")
        return None
        
    # Known equipment class patterns (standard equipment types)
    # NOTE: This is a hard-coded list for safety during the proof of concept phase.
    # TODO: In the future, this will be expanded or replaced with a more flexible mechanism
    # for equipment class identification (e.g., from configuration or database).
    known_equipment_classes = [
        "Filler", "Cartoner", "Bundler", "CaseFormer", "CasePacker", 
        "CaseSealer", "Palletizer"
    ]
    
    # --- Parse from EQUIPMENT_NAME ---
    if equipment_name and isinstance(equipment_name, str):
        # Case 1: Names with underscores (FIPCO009_Filler)
        if '_' in equipment_name:
            parts = equipment_name.split('_')
            class_part = parts[-1]

            # Try to extract base class name by removing trailing digits
            base_class = re.sub(r'\d+$', '', class_part)

            # Validate the base class name
            if base_class and re.search(r'[a-zA-Z]', base_class):
                # Further validate that this looks like an equipment class and not a line ID
                if not base_class.startswith("FIPCO"):
                    pop_logger.debug(f"Parsed equipment class '{base_class}' from '{equipment_name}'")
                    return base_class
                else:
                    pop_logger.warning(f"Part after underscore '{base_class}' looks like a line ID, not a valid equipment class")
        
        # Case 2: Check for equipment names that match known classes with potential trailing numbers
        # First try exact/direct matching
        for known_class in known_equipment_classes:
            # Check if the equipment name IS the class name (with optional trailing digits)
            class_pattern = re.compile(f"^{known_class}\\d*$", re.IGNORECASE)
            if class_pattern.match(equipment_name):
                pop_logger.debug(f"Matched equipment name '{equipment_name}' to class '{known_class}'")
                return known_class
            
            # Alternatively check if name starts with known class
            if equipment_name.startswith(known_class):
                # Check if what follows is just digits
                remainder = equipment_name[len(known_class):]
                if not remainder or remainder.isdigit() or remainder[0].isdigit():
                    pop_logger.debug(f"Extracted equipment class '{known_class}' from '{equipment_name}'")
                    return known_class
            
            # Also look for known class within the name
            if known_class in equipment_name:
                # Only use this if we can't determine a more specific match
                pop_logger.debug(f"Found equipment class '{known_class}' within '{equipment_name}'")
                return known_class
        
        # Case 3: Handle model-specific patterns in equipment name
        # Not returning any special model names as classes, as requested
        
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
               - equipment_class_info: (Optional) Tuple with class name, individual, and position
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
    if eq_type.lower() != 'equipment':
        # Skip non-equipment types
        return None, None, None
    
    # Get equipment ID mappings if defined, otherwise default to EQUIPMENT_NAME
    eq_id_map = property_mappings.get('Equipment', {}).get('data_properties', {}).get('equipmentId')
    eq_id_col = eq_id_map.get('column') if eq_id_map else 'EQUIPMENT_NAME'
    eq_id_value = row.get(eq_id_col, eq_name).strip() if eq_id_col in row else eq_name
    
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
    
    # Optionally add the original EQUIPMENT_NAME as a label if we parsed
    if is_parsed_from_name and eq_class_id_value and eq_class_id_value != eq_class_base_name:
        if eq_class_id_value not in eq_class_labels:
            eq_class_labels.append(f"Source Name: {eq_class_id_value}")
    # Optionally add name from dedicated name column if different from ID source and base name
    elif eq_class_name_map and eq_class_name_map.get('column') != eq_class_col:
        class_name_val = safe_cast(row.get(eq_class_name_map['column']), str)
        if class_name_val and class_name_val not in eq_class_labels:
             eq_class_labels.append(class_name_val)

    eq_class_ind = get_or_create_individual(cls_EquipmentClass, eq_class_base_name, context.onto, all_created_individuals_by_uid, add_labels=eq_class_labels)

    # Ensure the equipmentClassId data property is set with the correct base name
    prop_equipmentClassId = context.get_prop("equipmentClassId")
    if eq_class_ind and prop_equipmentClassId:
        context.set_prop(eq_class_ind, "equipmentClassId", eq_class_base_name)
        pop_logger.debug(f"Explicitly set equipmentClassId='{eq_class_base_name}' on individual {eq_class_ind.name}")

    # Initialize sequence position to None
    eq_class_pos = None

    if eq_class_ind and pass_num == 1 and "EquipmentClass" in property_mappings:
        # Get property for sequence position
        prop_defaultSequencePosition = context.get_prop("defaultSequencePosition")
        if not prop_defaultSequencePosition:
            pop_logger.warning(f"Property 'defaultSequencePosition' not found in ontology. Sequence relationships won't be established.")
        
        # PRIORITY 1: First check if sequence position is already set on the individual
        if prop_defaultSequencePosition:
            current_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
            if current_pos is not None:
                eq_class_pos = safe_cast(current_pos, int)
                pop_logger.debug(f"Equipment class '{eq_class_base_name}' already has sequence position {eq_class_pos}")
        
        # PRIORITY 2: Check if there's a mapping for defaultSequencePosition in the data
        sequence_pos_mapping = property_mappings.get('EquipmentClass', {}).get('data_properties', {}).get('defaultSequencePosition')
        sequence_pos_column = sequence_pos_mapping.get('column') if sequence_pos_mapping else None
        
        # Try to get sequence position from mapped column if available and position not already set
        if eq_class_pos is None and sequence_pos_column and sequence_pos_column in row:
            raw_pos_from_data = row.get(sequence_pos_column)
            # Use safe_cast to convert to integer
            pos_from_data = safe_cast(raw_pos_from_data, int)
            if pos_from_data is not None:
                # Set the position directly from data
                if prop_defaultSequencePosition:
                    context.set_prop(eq_class_ind, "defaultSequencePosition", pos_from_data)
                eq_class_pos = pos_from_data
                pop_logger.info(f"Set sequence position {pos_from_data} for equipment class '{eq_class_base_name}' from column '{sequence_pos_column}'")
            else:
                pop_logger.debug(f"Column '{sequence_pos_column}' exists but value '{raw_pos_from_data}' could not be cast to int")
        
        # Apply all other mapped data properties
        apply_data_property_mappings(eq_class_ind, property_mappings["EquipmentClass"], row, context, "EquipmentClass", pop_logger)
        
        # PRIORITY 3: If no position was set from mapped column, try config
        if eq_class_pos is None:
            # Check if position was set by apply_data_property_mappings
            raw_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
            eq_class_pos = safe_cast(raw_pos, int) if raw_pos is not None else None
            
            # If still no position, try using the default from config
            if eq_class_pos is None:
                from ontology_generator.config import DEFAULT_EQUIPMENT_SEQUENCE
                
                if eq_class_base_name in DEFAULT_EQUIPMENT_SEQUENCE:
                    default_pos = DEFAULT_EQUIPMENT_SEQUENCE.get(eq_class_base_name)
                    pop_logger.info(f"Using default sequence position {default_pos} for equipment class '{eq_class_base_name}' from config.DEFAULT_EQUIPMENT_SEQUENCE")
                    # Set the position in the individual
                    if prop_defaultSequencePosition:
                        context.set_prop(eq_class_ind, "defaultSequencePosition", default_pos)
                    eq_class_pos = default_pos
                else:
                    pop_logger.warning(f"No sequence position available for equipment class '{eq_class_base_name}' - not in mapped column or config defaults")
                    pop_logger.warning(f"Add '{eq_class_base_name}' to DEFAULT_EQUIPMENT_SEQUENCE in config.py with an appropriate position value")
        
        # Prepare info for tracking
        eq_class_info_out = (eq_class_base_name, eq_class_ind, eq_class_pos)
        
        # Add some validation logging to verify the position was properly set
        final_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
        if final_pos is not None:
            pop_logger.debug(f"Verified equipment class '{eq_class_base_name}' has defaultSequencePosition set to {final_pos}")
        else:
            pop_logger.warning(f"Equipment class '{eq_class_base_name}' still has no defaultSequencePosition after all attempts")
            
        # Create equipment individual if we have a class
        eq_ind = get_or_create_individual(cls_Equipment, eq_id_value, context.onto, all_created_individuals_by_uid)
        
        # Set basic equipment properties
        if eq_ind and pass_num == 1 and "Equipment" in property_mappings:
            # Set equipmentId property
            prop_equipmentId = context.get_prop("equipmentId")
            if prop_equipmentId:
                context.set_prop(eq_ind, "equipmentId", eq_id_value)
            
            # Link equipment to equipment class
            prop_memberOfClass = context.get_prop("memberOfClass")
            if prop_memberOfClass and eq_class_ind:
                context.set_prop(eq_ind, "memberOfClass", eq_class_ind)
                pop_logger.debug(f"Linked Equipment {eq_ind.name} to EquipmentClass {eq_class_ind.name}")
            
            # Link equipment to production line
            if line_ind:
                prop_isPartOfProductionLine = context.get_prop("isPartOfProductionLine")
                if prop_isPartOfProductionLine:
                    # Store line ID in Equipment for use in post-processing
                    line_id = getattr(line_ind, "lineId", line_ind.name)
                    context.set_prop(eq_ind, "associatedLineId", line_id)
                    
                    # Link equipment to line
                    context.set_prop(eq_ind, "isPartOfProductionLine", line_ind)
                    pop_logger.debug(f"Linked Equipment {eq_ind.name} to ProductionLine {line_ind.name}")
            
            # Apply mapped data properties
            apply_data_property_mappings(eq_ind, property_mappings["Equipment"], row, context, "Equipment", pop_logger)
            
            # Only apply object properties in Pass 2
            if pass_num == 2:
                apply_object_property_mappings(eq_ind, property_mappings["Equipment"], row, context, "Equipment", pop_logger)

    # Return both created/retrieved individuals
    return eq_ind, eq_class_ind, eq_class_info_out
