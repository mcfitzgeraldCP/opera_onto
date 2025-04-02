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
    Processes Equipment and its associated EquipmentClass from a row.

    Pass 1: Creates individuals, applies data properties, adds to registry, collects class info.
    Pass 2: (Currently not handled here, linking done by apply_object_property_mappings)

    Relies on property_mappings for Equipment and EquipmentClass.
    Assumes IDs for Equipment and EquipmentClass can be found via mappings.

    Args:
        row: The data row.
        context: Population context.
        property_mappings: Property mappings dictionary.
        all_created_individuals_by_uid: Central individual registry.
        line_ind: The ProductionLine individual associated with this row (for context).
        pass_num: The current population pass (1 or 2).

    Returns:
        Tuple: (equipment_individual, equipment_class_individual, equipment_class_info)
               - equipment_individual: The created/retrieved Equipment individual.
               - equipment_class_individual: The created/retrieved EquipmentClass individual.
               - equipment_class_info: Tuple (class_name, class_ind, position) for tracking.
    """
    if not property_mappings:
        pop_logger.warning("Property mappings not provided to process_equipment_and_class. Skipping.")
        return None, None, None
    if all_created_individuals_by_uid is None:
         pop_logger.error("Individual registry not provided to process_equipment_and_class. Skipping.")
         return None, None, None

    # Get classes
    cls_Equipment = context.get_class("Equipment")
    cls_EquipmentClass = context.get_class("EquipmentClass")
    if not cls_Equipment or not cls_EquipmentClass:
        pop_logger.error("Essential classes 'Equipment' or 'EquipmentClass' not found. Cannot process equipment.")
        return None, None, None

    equipment_ind: Optional[Thing] = None
    eq_class_ind: Optional[Thing] = None
    eq_class_info_out: Optional[Tuple] = None

    # --- 1. Process Equipment Class ---
    # Equipment Class is often needed before Equipment (for linking memberOfClass)
    # We need a unique identifier for the class. Often the name itself, or a dedicated ID column.

    # Attempt 1: Use equipmentClassId property mapping
    eq_class_id_map = property_mappings.get('EquipmentClass', {}).get('data_properties', {}).get('equipmentClassId')
    eq_class_name_map = property_mappings.get('EquipmentClass', {}).get('data_properties', {}).get('equipmentClassName') # Optional name
    eq_class_col = None
    eq_class_id_value = None # Raw value from the determined column
    eq_class_base_name = None # The final name/ID to use for the class individual
    is_parsed_from_name = False # Flag to track if we used parsing

    if eq_class_id_map and eq_class_id_map.get('column'):
        eq_class_col = eq_class_id_map['column']
        eq_class_id_value = safe_cast(row.get(eq_class_col), str) # Get raw value
        pop_logger.debug(f"Found EquipmentClass.equipmentClassId mapping to column '{eq_class_col}'")
        
        # *** ENHANCED LOGIC: Check multiple sources for class determination ***
        # Prepare additional sources for class determination
        equipment_type = safe_cast(row.get('EQUIPMENT_TYPE'), str) if 'EQUIPMENT_TYPE' in row else None
        equipment_name = safe_cast(row.get('EQUIPMENT_NAME'), str) if 'EQUIPMENT_NAME' in row else None
        
        # IMPORTANT: Only use EQUIPMENT_NAME for determining equipment class, not other columns
        if not equipment_name:
            pop_logger.warning(f"Missing EQUIPMENT_NAME column or value. Cannot determine equipment class.")
            return None, None, None

        # Log what we're using for class determination
        pop_logger.debug(f"Using EQUIPMENT_NAME='{equipment_name}' for equipment class determination")
        
        # Try to determine class using parse_equipment_class with ONLY equipment_name
        eq_class_base_name = parse_equipment_class(
            equipment_name=equipment_name,
            equipment_type=equipment_type,
            # Not passing equipment_model, model, or complexity to ensure we only parse from equipment_name
        )
        is_parsed_from_name = True
        
        if not eq_class_base_name:
            pop_logger.warning(f"Failed to determine equipment class from EQUIPMENT_NAME='{equipment_name}'. Skipping equipment class processing.")
            # Skip further class processing if parsing fails from equipment_name
            return None, None, None
        else:
            pop_logger.debug(f"Determined equipment class name: '{eq_class_base_name}' from EQUIPMENT_NAME")
    else:
        # Don't attempt to use alternative sources - only EQUIPMENT_NAME is valid
        pop_logger.warning("No mapping for equipmentClassId found. Will attempt to use EQUIPMENT_NAME directly.")
        equipment_name = safe_cast(row.get('EQUIPMENT_NAME'), str) if 'EQUIPMENT_NAME' in row else None
        
        if not equipment_name:
            pop_logger.warning("EQUIPMENT_NAME column not found or empty. Cannot determine equipment class.")
            return None, None, None
            
        equipment_type = safe_cast(row.get('EQUIPMENT_TYPE'), str) if 'EQUIPMENT_TYPE' in row else None
        
        # Try to parse from EQUIPMENT_NAME
        eq_class_base_name = parse_equipment_class(
            equipment_name=equipment_name,
            equipment_type=equipment_type
        )
        
        if not eq_class_base_name:
            pop_logger.warning(f"Failed to determine equipment class from EQUIPMENT_NAME='{equipment_name}'. Skipping equipment class processing.")
            return None, None, None
            
        pop_logger.debug(f"Determined equipment class name: '{eq_class_base_name}' from EQUIPMENT_NAME")

    # Check if we obtained a base name
    if not eq_class_base_name:
        pop_logger.warning(f"Missing or invalid EquipmentClass ID/Name from column '{eq_class_col}' (value: '{eq_class_id_value}'). Skipping EquipmentClass processing.")
        return None, None, None

    # Now use eq_class_base_name for creating the individual
    eq_class_labels = [eq_class_base_name]
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
        # First check if there's a mapping for defaultSequencePosition
        sequence_pos_mapping = property_mappings.get('EquipmentClass', {}).get('data_properties', {}).get('defaultSequencePosition')
        sequence_pos_column = sequence_pos_mapping.get('column') if sequence_pos_mapping else None
        
        # Try to get sequence position from mapped column if available
        if sequence_pos_column and sequence_pos_column in row:
            raw_pos_from_data = row.get(sequence_pos_column)
            # Use safe_cast to convert to integer
            pos_from_data = safe_cast(raw_pos_from_data, int)
            if pos_from_data is not None:
                # Set the position directly from data
                context.set_prop(eq_class_ind, "defaultSequencePosition", pos_from_data)
                eq_class_pos = pos_from_data
                pop_logger.info(f"Set sequence position {pos_from_data} for equipment class '{eq_class_base_name}' from column '{sequence_pos_column}'")
            else:
                pop_logger.debug(f"Column '{sequence_pos_column}' exists but value '{raw_pos_from_data}' could not be cast to int")
        
        # Apply all other mapped data properties
        apply_data_property_mappings(eq_class_ind, property_mappings["EquipmentClass"], row, context, "EquipmentClass", pop_logger)
        
        # If no position was set from mapped column, check if we already have one from prior processing or try config
        if eq_class_pos is None:
            # Check if position was set by apply_data_property_mappings
            raw_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
            eq_class_pos = safe_cast(raw_pos, int) if raw_pos is not None else None
            
            # If still no position, try using the default from config
            if eq_class_pos is None and eq_class_base_name in DEFAULT_EQUIPMENT_SEQUENCE:
                default_pos = DEFAULT_EQUIPMENT_SEQUENCE.get(eq_class_base_name)
                pop_logger.info(f"Using default sequence position {default_pos} for equipment class '{eq_class_base_name}' from config.DEFAULT_EQUIPMENT_SEQUENCE")
                # Set the position in the individual
                context.set_prop(eq_class_ind, "defaultSequencePosition", default_pos)
                eq_class_pos = default_pos
            elif eq_class_pos is None:
                pop_logger.debug(f"No sequence position available for equipment class '{eq_class_base_name}' (not in mapped column or config defaults)")
        
        # Prepare info for tracking
        eq_class_info_out = (eq_class_base_name, eq_class_ind, eq_class_pos)
        
        # Add some validation logging to verify the position was properly set
        final_pos = getattr(eq_class_ind, "defaultSequencePosition", None)
        if final_pos is not None:
            pop_logger.debug(f"Verified equipment class '{eq_class_base_name}' has defaultSequencePosition set to {final_pos}")
        else:
            pop_logger.warning(f"Equipment class '{eq_class_base_name}' still has no defaultSequencePosition after all attempts")

    elif not eq_class_ind:
        pop_logger.warning(f"Failed to create/retrieve EquipmentClass individual for base '{eq_class_base_name}'. Equipment processing might be incomplete.")
        # Continue to process Equipment if possible, but linking to class will fail later

    # --- 2. Process Equipment --- 
    # Equipment needs an ID
    equip_id_map = property_mappings.get('Equipment', {}).get('data_properties', {}).get('equipmentId')
    if not equip_id_map or not equip_id_map.get('column'):
        pop_logger.warning("Cannot determine the column for Equipment.equipmentId from property mappings. Skipping Equipment creation.")
        return None, eq_class_ind, eq_class_info_out # Return class if created
    equip_id_col = equip_id_map['column']
    equip_id = safe_cast(row.get(equip_id_col), str)
    if not equip_id:
        pop_logger.warning(f"Missing or invalid Equipment ID in column '{equip_id_col}'. Skipping Equipment creation.")
        return None, eq_class_ind, eq_class_info_out # Return class if created

    # Equipment name needs context (line) for uniqueness if ID is not globally unique
    # Using LineID_EquipmentID as base name
    line_id_str = line_ind.lineId[0] if line_ind and hasattr(line_ind, 'lineId') and line_ind.lineId else "UnknownLine"
    equip_unique_base = f"{line_id_str}_{equip_id}"
    
    # Try to get name for label
    equip_name_map = property_mappings.get('Equipment', {}).get('data_properties', {}).get('equipmentName')
    equip_name = None
    if equip_name_map and equip_name_map.get('column'):
         equip_name = safe_cast(row.get(equip_name_map['column']), str)
         
    equip_labels = [equip_id]
    if equip_name:
        equip_labels.append(equip_name)
    else: # Use unique base if name missing
        equip_labels.append(equip_unique_base) 
        
    equipment_ind = get_or_create_individual(cls_Equipment, equip_unique_base, context.onto, all_created_individuals_by_uid, add_labels=equip_labels)

    if equipment_ind and pass_num == 1 and "Equipment" in property_mappings:
        # Linking (isPartOfProductionLine, memberOfClass, isUpstreamOf etc.) happens in Pass 2
        apply_data_property_mappings(equipment_ind, property_mappings["Equipment"], row, context, "Equipment", pop_logger)

        # --- Special Handling for memberOfClass in Pass 1? ---
        # While full linking is in Pass 2, memberOfClass is crucial and links to the class *we just processed*.
        # It might be beneficial to set this single object property here if the class exists.
        # However, the generic apply_object_property_mappings in Pass 2 should handle it via the registry.
        # Let's stick to the strict separation for now.
        # if eq_class_ind and context.get_prop("memberOfClass"):
        #     if not getattr(equipment_ind, "memberOfClass", None): # Set only if not already set (e.g., by prior run)
        #         context.set_prop(equipment_ind, "memberOfClass", eq_class_ind)
        #         pop_logger.debug(f"Set memberOfClass link for {equipment_ind.name} to {eq_class_ind.name} during Pass 1.")
        # elif not eq_class_ind:
        #      pop_logger.warning(f"Cannot set memberOfClass for {equipment_ind.name} in Pass 1: EquipmentClass individual is missing.")
        pass # Defer memberOfClass linking to Pass 2

    elif not equipment_ind:
         pop_logger.warning(f"Failed to create/retrieve Equipment individual for base '{equip_unique_base}'.")
         # Return class if created
         return None, eq_class_ind, eq_class_info_out

    return equipment_ind, eq_class_ind, eq_class_info_out
