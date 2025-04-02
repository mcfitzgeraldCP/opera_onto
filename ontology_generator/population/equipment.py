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
    PopulationContext, get_or_create_individual, apply_property_mappings,
    apply_data_property_mappings, apply_object_property_mappings
)

def parse_equipment_class(equipment_name: Optional[str]) -> Optional[str]:
    """
    Parses the EquipmentClass from the EQUIPMENT_NAME.
    
    Rules:
    1. Extracts the part after the last underscore
    2. Removes trailing digits from class name to handle instance identifiers
    3. Validates the resulting class name has letters
    4. Falls back to appropriate alternatives if validation fails
    
    Args:
        equipment_name: The equipment name to parse
        
    Returns:
        The parsed equipment class name or None
    
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
    eq_class_id_from_map = None

    if eq_class_id_map and eq_class_id_map.get('column'):
        eq_class_col = eq_class_id_map['column']
        eq_class_id_from_map = safe_cast(row.get(eq_class_col), str)
        pop_logger.debug(f"Using EquipmentClass.equipmentClassId mapping (column '{eq_class_col}') for class ID.")
    else:
        # Attempt 2: Fallback to using equipmentClassName property mapping as the ID source
        if eq_class_name_map and eq_class_name_map.get('column'):
            eq_class_col = eq_class_name_map['column']
            eq_class_id_from_map = safe_cast(row.get(eq_class_col), str)
            pop_logger.debug(f"Falling back to EquipmentClass.equipmentClassName mapping (column '{eq_class_col}') for class ID.")
        else:
            pop_logger.warning("Cannot determine column for EquipmentClass ID (tried equipmentClassId, equipmentClassName). Skipping EquipmentClass processing.")
            # Cannot proceed without class ID
            return None, None, None

    if not eq_class_id_from_map:
        pop_logger.warning(f"Missing or invalid EquipmentClass ID/Name in column '{eq_class_col}'. Skipping EquipmentClass processing.")
        return None, None, None

    # Use the found ID/Name as the base for the individual name and registry key
    eq_class_base_name = eq_class_id_from_map
    eq_class_labels = [eq_class_base_name]
    # Optionally add name from name column if different from ID column
    if eq_class_name_map and eq_class_name_map.get('column') != eq_class_col:
        class_name_val = safe_cast(row.get(eq_class_name_map['column']), str)
        if class_name_val and class_name_val not in eq_class_labels:
             eq_class_labels.append(class_name_val)

    eq_class_ind = get_or_create_individual(cls_EquipmentClass, eq_class_base_name, context.onto, all_created_individuals_by_uid, add_labels=eq_class_labels)

    eq_class_pos = None
    if eq_class_ind and pass_num == 1 and "EquipmentClass" in property_mappings:
        apply_data_property_mappings(eq_class_ind, property_mappings["EquipmentClass"], row, context, "EquipmentClass", pop_logger)
        # Extract sequence position after applying data properties
        pos_prop_name = "defaultSequencePosition"
        if context.get_prop(pos_prop_name):
            try:
                # Use safe_cast directly on the potential attribute value
                # getattr might return None or the value
                raw_pos = getattr(eq_class_ind, pos_prop_name, None)
                eq_class_pos = safe_cast(raw_pos, int) if raw_pos is not None else None
            except Exception as e:
                 pop_logger.warning(f"Could not read or cast {pos_prop_name} for {eq_class_ind.name}: {e}")
        # Prepare info for tracking
        eq_class_info_out = (eq_class_base_name, eq_class_ind, eq_class_pos)

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
