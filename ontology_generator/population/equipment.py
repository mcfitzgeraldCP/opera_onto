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
    PopulationContext, get_or_create_individual, apply_property_mappings
)
from ontology_generator.config import DEFAULT_EQUIPMENT_SEQUENCE

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

def process_equipment(row: Dict[str, Any], 
                      context: PopulationContext, 
                      line_ind: Optional[Thing], 
                      property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
                     ) -> Tuple[Optional[Thing], Optional[Thing], Optional[str]]:
    """
    Processes Equipment and its associated EquipmentClass from a row.
    
    Args:
        row: The data row
        context: The population context
        line_ind: The associated production line individual
        property_mappings: Optional property mappings dictionary
        
    Returns:
        A tuple of (equipment_individual, equipment_class_individual, equipment_class_name)
    """
    cls_Equipment = context.get_class("Equipment")
    cls_EquipmentClass = context.get_class("EquipmentClass")
    if not cls_Equipment or not cls_EquipmentClass: 
        return None, None, None

    eq_id_str = safe_cast(row.get('EQUIPMENT_ID'), str)
    if not eq_id_str:
        pop_logger.debug("No EQUIPMENT_ID in row, skipping equipment creation.")
        return None, None, None

    eq_name = safe_cast(row.get('EQUIPMENT_NAME'), str)
    eq_unique_base = eq_id_str  # Assume equipment ID is unique enough
    eq_labels = [f"ID:{eq_id_str}"]
    if eq_name: 
        eq_labels.insert(0, eq_name)

    equipment_ind = get_or_create_individual(cls_Equipment, eq_unique_base, context.onto, add_labels=eq_labels)
    if not equipment_ind:
        pop_logger.error(f"Failed to create Equipment individual for ID '{eq_id_str}'.")
        return None, None, None  # Cannot proceed without equipment individual

    # Check if we can use dynamic property mappings for Equipment
    if property_mappings and "Equipment" in property_mappings:
        equipment_mappings = property_mappings["Equipment"]
        apply_property_mappings(equipment_ind, equipment_mappings, row, context, "Equipment")
        # Link Equipment to ProductionLine (not in mappings)
        if line_ind:
            context.set_prop(equipment_ind, "isPartOfProductionLine", line_ind)
    else:
        # Fallback to hardcoded property assignments
        pop_logger.debug("Using hardcoded property assignments for Equipment (no dynamic mappings available)")
        # --- Set Equipment Properties ---
        context.set_prop(equipment_ind, "equipmentId", eq_id_str)
        if eq_name: 
            context.set_prop(equipment_ind, "equipmentName", eq_name)
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
            
            # Check if we can use dynamic property mappings for EquipmentClass
            if property_mappings and "EquipmentClass" in property_mappings:
                eqclass_mappings = property_mappings["EquipmentClass"]
                apply_property_mappings(eq_class_ind, eqclass_mappings, row, context, "EquipmentClass")
                # Also set equipment class ID if not set by mappings
                if not getattr(eq_class_ind, "equipmentClassId", None):
                    context.set_prop(eq_class_ind, "equipmentClassId", eq_class_name)
            else:
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
