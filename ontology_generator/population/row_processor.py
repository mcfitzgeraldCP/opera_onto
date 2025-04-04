import logging
from typing import Any, Dict, Optional, Tuple, List
from owlready2 import Thing

# Assuming imports for processing functions from other modules
from .asset import process_asset_hierarchy, process_material, process_production_request
from .equipment import process_equipment_and_class
from .events import process_event_related
# Need Person processing if added?
# from .person import process_person

# Import core components needed
from .core import PopulationContext, apply_object_property_mappings

# Logger setup
row_proc_logger = logging.getLogger(__name__)

# Type Alias for the central registry
IndividualRegistry = Dict[Tuple[str, str], Thing] # Key: (entity_type_str, unique_id_str), Value: Individual Object
RowIndividuals = Dict[str, Thing] # Key: entity_type_str, Value: Individual Object for this row


def process_single_data_row_pass1(
    row: Dict[str, Any],
    row_num: int,
    context: PopulationContext,
    property_mappings: Dict[str, Dict[str, Dict[str, Any]]],
    all_created_individuals_by_uid: IndividualRegistry
) -> Tuple[bool, RowIndividuals, Optional[Tuple], Optional[Tuple]]:
    """
    Processes a single data row during Pass 1: Creates individuals and applies data properties.

    Args:
        row: The data row dictionary.
        row_num: The original row number (for logging).
        context: The PopulationContext.
        property_mappings: The parsed property mappings.
        all_created_individuals_by_uid: The central registry to populate and use for get_or_create.

    Returns:
        Tuple: (success_flag, created_individuals_in_row, event_context_tuple, eq_class_info_tuple)
               - success_flag (bool): True if the essential parts of the row were processed.
               - created_individuals_in_row (Dict[str, Thing]): Individuals created/retrieved for this row.
               - event_context_tuple (Optional[Tuple]): Context for linking events later.
               - eq_class_info_tuple (Optional[Tuple]): Info for equipment class tracking.
    """
    row_proc_logger.debug(f"Row {row_num} - Pass 1 Start")
    created_inds_this_row: RowIndividuals = {}
    event_context = None
    eq_class_info = None
    success = True # Assume success unless critical failure
    critical_event_failure = False # TKT-006: Track critical failures in event processing

    try:
        # Add row_num to the row dictionary for use by downstream processors
        row['row_num'] = row_num
        
        # --- 1. Process Asset Hierarchy (Plant, Area, ProcessCell, ProductionLine) ---
        plant_ind, area_ind, pcell_ind, line_ind = process_asset_hierarchy(
            row, context, property_mappings, all_created_individuals_by_uid, pass_num=1
        )
        if plant_ind: created_inds_this_row["Plant"] = plant_ind
        if area_ind: created_inds_this_row["Area"] = area_ind
        if pcell_ind: created_inds_this_row["ProcessCell"] = pcell_ind
        if line_ind: created_inds_this_row["ProductionLine"] = line_ind
        if not plant_ind:
             row_proc_logger.error(f"Row {row_num} - Pass 1: Failed to process mandatory Plant. Aborting row.")
             return False, {}, None, None

        # --- 2. Process Equipment & Equipment Class ---
        equipment_ind, eq_class_ind, eq_class_info_out = None, None, None
        
        # Check EQUIPMENT_TYPE to determine if we should process equipment
        equipment_type = row.get('EQUIPMENT_TYPE', '').strip() if 'EQUIPMENT_TYPE' in row else 'Equipment'
        
        if equipment_type == 'Equipment':
            # Only process equipment and class if it's actually an equipment type
            equipment_ind, eq_class_ind, eq_class_info_out = process_equipment_and_class(
                row, context, property_mappings, all_created_individuals_by_uid, line_ind, pass_num=1
            )
            if equipment_ind: created_inds_this_row["Equipment"] = equipment_ind
            if eq_class_ind: created_inds_this_row["EquipmentClass"] = eq_class_ind
            if eq_class_info_out: eq_class_info = eq_class_info_out
        else:
            row_proc_logger.debug(f"Row {row_num} - Not processing equipment for EQUIPMENT_TYPE='{equipment_type}'")

        # --- 3. Process Material ---
        material_ind = process_material(row, context, property_mappings, all_created_individuals_by_uid, pass_num=1)
        if material_ind: created_inds_this_row["Material"] = material_ind

        # --- 4. Process Production Request ---
        request_ind = process_production_request(row, context, property_mappings, all_created_individuals_by_uid, pass_num=1)
        if request_ind: created_inds_this_row["ProductionRequest"] = request_ind

        # --- 5. Process Events (EventRecord, TimeInterval, Shift, State, Reason) ---
        event_related_inds, event_context_out = process_event_related(
            row, context, property_mappings, all_created_individuals_by_uid,
            equipment_ind=equipment_ind,
            line_ind=line_ind,
            material_ind=material_ind, # Pass context
            request_ind=request_ind, # Pass context
            pass_num=1,
            row_num=row_num  # Pass the actual row number explicitly
        )
        created_inds_this_row.update(event_related_inds)
        if event_context_out: 
            event_context = event_context_out
        else:
            # TKT-006: Track critical failure if we expected events but none were created
            if 'EVENT_TYPE' in row and row.get('EVENT_TYPE', '').strip():
                row_proc_logger.warning(f"Row {row_num} - Pass 1: Missing critical event context for event with type '{row.get('EVENT_TYPE')}'. Marking row as failed.")
                critical_event_failure = True
                # Don't return immediately, continue processing to gather all potential errors

        # --- 6. Process Person (Example) ---
        # person_ind = process_person(row, context, property_mappings, all_created_individuals_by_uid, pass_num=1)
        # if person_ind: created_inds_this_row["Person"] = person_ind

        row_proc_logger.debug(f"Row {row_num} - Pass 1 End. Created/found {len(created_inds_this_row)} individuals.")

    except Exception as e:
        row_proc_logger.error(f"Row {row_num} - Pass 1: Critical error processing row: {e}", exc_info=True)
        success = False
        created_inds_this_row = {} # Clear partial results on error
    finally:
        # Clean up row dictionary by removing temporary row_num 
        if 'row_num' in row:
            del row['row_num']

    # TKT-006: Final success check including critical event failures
    if critical_event_failure:
        success = False

    return success, created_inds_this_row, event_context, eq_class_info


def process_single_data_row_pass2(
    row: Dict[str, Any],
    row_num: int,
    context: PopulationContext,
    property_mappings: Dict[str, Dict[str, Dict[str, Any]]],
    individuals_in_row: RowIndividuals,
    linking_context: IndividualRegistry
) -> bool:
    """
    Processes a single data row during Pass 2: Applies object property mappings.

    Args:
        row: The data row dictionary.
        row_num: The original row number (for logging).
        context: The PopulationContext.
        property_mappings: The parsed property mappings.
        individuals_in_row: Dictionary of individuals created/retrieved for THIS row in Pass 1.
        linking_context: The central registry of ALL created individuals from Pass 1.

    Returns:
        bool: True if linking was attempted successfully (even if some links failed safely), False on critical error.
    """
    row_proc_logger.debug(f"Row {row_num} - Pass 2 Start")
    success = True # Assume success unless critical error

    # Add row_num to row dict temporarily for potential use in logging within apply funcs
    row['row_num'] = row_num 

    try:
        # Iterate through the individuals created for this row in Pass 1
        for entity_type, individual in individuals_in_row.items():
            if not individual:
                continue

            if entity_type in property_mappings:
                # Apply object property mappings for this entity type using the full context
                # But exclude structural properties which will be handled in a separate post-processing step
                apply_object_property_mappings(
                    individual,
                    property_mappings[entity_type],
                    row,
                    context,
                    entity_type,
                    row_proc_logger,
                    linking_context,
                    individuals_in_row,
                    exclude_structural=True
                )

        row_proc_logger.debug(f"Row {row_num} - Pass 2 End.")

    except Exception as e:
        row_proc_logger.error(f"Row {row_num} - Pass 2: Critical error during linking: {e}", exc_info=True)
        success = False
    finally:
        # Clean up temporary key
        if 'row_num' in row: del row['row_num']

    return success 

def process_structural_relationships(
    context: PopulationContext,
    property_mappings: Dict[str, Dict[str, Dict[str, Any]]],
    all_created_individuals_by_uid: IndividualRegistry,
    logger=None
) -> int:
    """
    Post-processing function that establishes structural relationships between individuals that were created
    from different rows. This addresses the limitation of row-based Pass 2 linking for structural properties.

    Args:
        context: The PopulationContext.
        property_mappings: The parsed property mappings.
        all_created_individuals_by_uid: The central registry of ALL created individuals.
        logger: Logger to use (defaults to row_proc_logger if None)

    Returns:
        int: The number of structural links created
    """
    # Use the provided logger or fall back to the module logger
    log = logger or row_proc_logger
    log.info("Starting post-processing of structural relationships...")
    
    # Structure to track links by type
    links_created = 0
    links_by_type = {}
    
    # Define known structural properties
    structural_properties = [
        "isPartOfProductionLine",      # Equipment -> ProductionLine
        "hasEquipmentPart",            # ProductionLine -> Equipment
        "memberOfClass"                # Equipment -> EquipmentClass
    ]
    
    # --- Process Equipment -> EquipmentClass relationships ---
    # CRITICAL FIX FOR TKT-002: Ensure correct memberOfClass links are established
    if "Equipment" in property_mappings and "object_properties" in property_mappings["Equipment"]:
        log.info("Processing Equipment.memberOfClass structural relationships...")
        
        # Get all Equipment individuals 
        equipment_individuals = [
            ind for uid, ind in all_created_individuals_by_uid.items() 
            if uid[0] == "Equipment"
        ]
        log.info(f"Found {len(equipment_individuals)} Equipment individuals for class linking")
        
        # Get all EquipmentClass individuals
        class_individuals = [
            ind for uid, ind in all_created_individuals_by_uid.items() 
            if uid[0] == "EquipmentClass"
        ]
        log.info(f"Found {len(class_individuals)} EquipmentClass individuals for linking")
        
        # Get the memberOfClass property mapping
        eq_class_mapping = property_mappings["Equipment"]["object_properties"].get("memberOfClass")
        
        if eq_class_mapping and equipment_individuals and class_individuals:
            # Check if the memberOfClass property exists
            member_of_class_prop = context.get_prop("memberOfClass")
            if not member_of_class_prop:
                log.error(f"CRITICAL: Required property 'memberOfClass' not found. Cannot link equipment to classes.")
            else:
                # Build a comprehensive lookup map for equipment classes by both ID and name
                classes_by_identifier = {}
                
                # Key properties that might identify an EquipmentClass
                identifiers = ["equipmentClassId", "equipmentClassName", "name"]
                
                # Log all EquipmentClass individuals with their identifiers for debugging
                log.debug("EquipmentClass individuals available for linking:")
                for class_ind in class_individuals:
                    class_identifiers = []
                    
                    # Collect all identifiers from the class individual
                    for id_prop in identifiers:
                        if hasattr(class_ind, id_prop):
                            id_value = getattr(class_ind, id_prop)
                            if id_value:
                                if isinstance(id_value, list):
                                    for val in id_value:
                                        class_identifiers.append(str(val))
                                else:
                                    class_identifiers.append(str(id_value))
                    
                    # Extract base name from the class name if it has a prefix
                    if hasattr(class_ind, "name"):
                        name = class_ind.name
                        if name.startswith("EquipmentClass_"):
                            class_identifiers.append(name[len("EquipmentClass_"):])
                    
                    # Add all identifiers to the lookup map
                    log.debug(f"  Class {class_ind.name} identifiers: {class_identifiers}")
                    for identifier in class_identifiers:
                        classes_by_identifier[identifier] = class_ind
                
                # Track linking results
                equipment_linked = 0
                equipment_already_linked = 0
                equipment_not_linked = 0
                
                # Iterate through equipment individuals
                for eq_ind in equipment_individuals:
                    # Check if this equipment already has a class link
                    current_class = getattr(eq_ind, member_of_class_prop.python_name, None)
                    if current_class:
                        log.debug(f"Equipment {eq_ind.name} already linked to class {current_class.name}")
                        equipment_already_linked += 1
                        continue
                    
                    # Try multiple methods to determine the appropriate class
                    
                    # Method 1: Try to use column value from mapping
                    matching_class_ind = None
                    match_method = None
                    
                    # Get the column that contains the Class name/ID (if specified in mapping)
                    class_id_column = eq_class_mapping.get("column")
                    if class_id_column:
                        # Get data stored in the equipment individual
                        eq_data = context.get_individual_data(eq_ind) or {}
                        class_value = eq_data.get(class_id_column)
                        
                        if class_value and str(class_value) in classes_by_identifier:
                            matching_class_ind = classes_by_identifier[str(class_value)]
                            match_method = f"Column '{class_id_column}'"
                    
                    # Method 2: Try to parse class from equipment name if column value not found
                    if not matching_class_ind:
                        from .equipment import parse_equipment_class
                        
                        # Try various properties that might contain the equipment name
                        name_props = ["equipmentName", "name"]
                        eq_name = None
                        
                        for prop in name_props:
                            if hasattr(eq_ind, prop):
                                prop_value = getattr(eq_ind, prop)
                                if prop_value:
                                    if isinstance(prop_value, list) and prop_value:
                                        eq_name = prop_value[0]
                                    else:
                                        eq_name = prop_value
                                    break
                        
                        if eq_name:
                            parsed_class = parse_equipment_class(equipment_name=eq_name)
                            if parsed_class and str(parsed_class) in classes_by_identifier:
                                matching_class_ind = classes_by_identifier[str(parsed_class)]
                                match_method = f"Parsed from name '{eq_name}'"
                    
                    # Method 3: Try direct name matching for any remaining unlinked equipment
                    if not matching_class_ind and hasattr(eq_ind, "name"):
                        eq_name = eq_ind.name
                        # Extract potential class name patterns from equipment name
                        from .equipment import parse_equipment_class
                        import re
                        
                        # Try to match with known patterns like "_ClassType"
                        if "_" in eq_name:
                            parts = eq_name.split("_")
                            for part in parts:
                                if part and part in classes_by_identifier:
                                    matching_class_ind = classes_by_identifier[part]
                                    match_method = f"Direct part match from '{eq_name}'"
                                    break
                        
                        # Try extracting capital word sequences that might be class names
                        if not matching_class_ind:
                            words = re.findall(r'[A-Z][a-zA-Z]*', eq_name)
                            for word in words:
                                if word and word in classes_by_identifier:
                                    matching_class_ind = classes_by_identifier[word]
                                    match_method = f"Capital word match from '{eq_name}'"
                                    break
                    
                    # Create the link if we found a matching class
                    if matching_class_ind:
                        try:
                            context.set_prop(eq_ind, "memberOfClass", matching_class_ind)
                            links_created += 1
                            equipment_linked += 1
                            log.info(f"Linked Equipment {eq_ind.name} to EquipmentClass {matching_class_ind.name} via {match_method}")
                            
                            # Record the link type for statistics
                            links_by_type["Equipment->Class"] = links_by_type.get("Equipment->Class", 0) + 1
                        except Exception as e:
                            log.error(f"Error linking Equipment {eq_ind.name} to Class {matching_class_ind.name}: {e}")
                    else:
                        equipment_not_linked += 1
                        log.warning(f"Could not determine appropriate class for Equipment {eq_ind.name}")
                
                # Log summary of Equipment-Class linking
                log.info(f"Equipment-Class linking summary:")
                log.info(f"  • Equipment already linked: {equipment_already_linked}")
                log.info(f"  • Equipment newly linked: {equipment_linked}")
                log.info(f"  • Equipment not linked: {equipment_not_linked}")
                log.info(f"  • Total equipment processed: {len(equipment_individuals)}")
    
    # Process Equipment -> ProductionLine relationships
    if "Equipment" in property_mappings and "object_properties" in property_mappings["Equipment"]:
        log.info("Processing Equipment.isPartOfProductionLine structural relationships...")
        
        # Get all Equipment individuals (if not already fetched)
        if 'equipment_individuals' not in locals():
            equipment_individuals = [
                ind for uid, ind in all_created_individuals_by_uid.items() 
                if uid[0] == "Equipment"
            ]
        
        # Get all ProductionLine individuals
        line_individuals = [
            ind for uid, ind in all_created_individuals_by_uid.items() 
            if uid[0] == "ProductionLine"
        ]
        
        # Get the isPartOfProductionLine property mapping
        eq_line_mapping = property_mappings["Equipment"]["object_properties"].get("isPartOfProductionLine")
        
        if eq_line_mapping and equipment_individuals and line_individuals:
            # The column that contains the Line ID for Equipment
            line_id_column = eq_line_mapping.get("column")
            
            if line_id_column:
                # First, build a lookup map for lines by their ID
                lines_by_id = {}
                line_id_prop = "lineId" # Property name expected to hold the ID value
                
                # Check if the lineId property exists
                line_id_obj_prop = context.get_prop(line_id_prop)
                if not line_id_obj_prop:
                    log.warning(f"Required property mapping '{line_id_prop}' not found. Cannot create line lookup map for structural relationships.")
                else:
                    for line_ind in line_individuals:
                        # Get the line's ID value from its properties
                        if hasattr(line_ind, line_id_prop) and getattr(line_ind, line_id_prop):
                            line_id = getattr(line_ind, line_id_prop)
                            if isinstance(line_id, list) and line_id:
                                for lid in line_id:
                                    lines_by_id[str(lid)] = line_ind
                            else:
                                lines_by_id[str(line_id)] = line_ind
                
                # Check for the isPartOfProductionLine and hasEquipmentPart properties
                is_part_of_line_prop = context.get_prop("isPartOfProductionLine")
                has_equipment_part_prop = context.get_prop("hasEquipmentPart")
                
                if not is_part_of_line_prop:
                    log.warning(f"Required property mapping 'isPartOfProductionLine' not found. Cannot link equipment to lines.")
                elif not has_equipment_part_prop:
                    log.warning(f"Required property mapping 'hasEquipmentPart' not found. Cannot link lines to equipment.")
                else:
                    # Track link counts
                    equipment_line_links = 0
                    
                    # Link equipment to lines
                    for eq_ind in equipment_individuals:
                        # Get data stored in the equipment individual
                        eq_data = context.get_individual_data(eq_ind) or {}
                        
                        # Get the line ID this equipment is part of
                        line_id_value = eq_data.get(line_id_column)
                        
                        if line_id_value and str(line_id_value) in lines_by_id:
                            # Get the corresponding line individual
                            line_ind = lines_by_id[str(line_id_value)]
                            
                            # Create bidirectional links if they don't exist
                            # Check if the equipment is already linked to this line
                            current_line = getattr(eq_ind, is_part_of_line_prop.python_name, None)
                            equipment_already_linked = False
                            
                            if current_line:
                                if isinstance(current_line, list):
                                    equipment_already_linked = line_ind in current_line
                                else:
                                    equipment_already_linked = current_line == line_ind
                            
                            if not equipment_already_linked:
                                context.set_prop(eq_ind, "isPartOfProductionLine", line_ind)
                                context.set_prop(line_ind, "hasEquipmentPart", eq_ind)
                                links_created += 1
                                equipment_line_links += 1
                                log.debug(f"Linked Equipment {eq_ind.name} to Line {line_ind.name} via isPartOfProductionLine/hasEquipmentPart")
                                
                                # Record the link type for statistics
                                links_by_type["Equipment->Line"] = links_by_type.get("Equipment->Line", 0) + 1
                    
                    log.info(f"Created {equipment_line_links} Equipment-Line links")
    
    # Log summary of links created
    for link_type, count in links_by_type.items():
        log.info(f"Created {count} {link_type} structural links")
    
    log.info(f"Post-processing complete: Created {links_created} structural links in total")
    return links_created 