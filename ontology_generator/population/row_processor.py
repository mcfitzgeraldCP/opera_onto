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
        if plant_ind: 
            created_inds_this_row["Plant"] = plant_ind
            # TKT-002: Store row data with individual
            context.store_individual_data(plant_ind, row)
            
        if area_ind: 
            created_inds_this_row["Area"] = area_ind
            context.store_individual_data(area_ind, row)
            
        if pcell_ind: 
            created_inds_this_row["ProcessCell"] = pcell_ind
            context.store_individual_data(pcell_ind, row)
            
        if line_ind: 
            created_inds_this_row["ProductionLine"] = line_ind
            context.store_individual_data(line_ind, row)
            
        if not plant_ind:
             row_proc_logger.error(f"Row {row_num} - Pass 1: Failed to process mandatory Plant. Aborting row.")
             return False, {}, None, None

        # --- 2. Process Equipment & Equipment Class ---
        equipment_ind, eq_class_ind, eq_class_info_out = None, None, None
        
        # TKT-003: Check EQUIPMENT_TYPE to determine if we should process equipment
        equipment_type = row.get('EQUIPMENT_TYPE', '').strip() if 'EQUIPMENT_TYPE' in row else 'Equipment'
        
        # TKT-003: Log the equipment type for traceability
        row_proc_logger.debug(f"Row {row_num} - TKT-003: Processing row with EQUIPMENT_TYPE='{equipment_type}'")
        
        if equipment_type == 'Equipment':
            # Only process equipment and class if it's actually an equipment type
            equipment_ind, eq_class_ind, eq_class_info_out = process_equipment_and_class(
                row, context, property_mappings, all_created_individuals_by_uid, line_ind, pass_num=1
            )
            if equipment_ind: 
                created_inds_this_row["Equipment"] = equipment_ind
                context.store_individual_data(equipment_ind, row)
                
            if eq_class_ind: 
                created_inds_this_row["EquipmentClass"] = eq_class_ind
                context.store_individual_data(eq_class_ind, row)
                
            if eq_class_info_out: eq_class_info = eq_class_info_out
        elif equipment_type == 'Line':
            row_proc_logger.debug(f"Row {row_num} - TKT-003: Row has EQUIPMENT_TYPE='Line', skipping equipment processing")
            # Verify that we have a line_ind for line events
            if not line_ind:
                row_proc_logger.warning(f"Row {row_num} - TKT-003: EQUIPMENT_TYPE is 'Line' but no line individual was created. Event linking may fail.")
        else:
            row_proc_logger.warning(f"Row {row_num} - TKT-003: Unknown EQUIPMENT_TYPE '{equipment_type}'. Expected 'Equipment' or 'Line'.")

        # --- 3. Process Material ---
        material_ind = process_material(row, context, property_mappings, all_created_individuals_by_uid, pass_num=1)
        if material_ind: 
            created_inds_this_row["Material"] = material_ind
            context.store_individual_data(material_ind, row)

        # --- 4. Process Production Request ---
        request_ind = process_production_request(row, context, property_mappings, all_created_individuals_by_uid, pass_num=1)
        if request_ind: 
            created_inds_this_row["ProductionRequest"] = request_ind
            context.store_individual_data(request_ind, row)

        # --- 5. Process Events (EventRecord, TimeInterval, Shift, State, Reason) ---
        # TKT-003: Verify appropriate resource is available based on EQUIPMENT_TYPE
        if equipment_type == 'Equipment' and not equipment_ind:
            row_proc_logger.warning(f"Row {row_num} - TKT-003: EQUIPMENT_TYPE is 'Equipment' but no equipment resource is available. Event creation may fail.")
        elif equipment_type == 'Line' and not line_ind:
            row_proc_logger.warning(f"Row {row_num} - TKT-003: EQUIPMENT_TYPE is 'Line' but no line resource is available. Event creation may fail.")
        
        event_related_inds, event_context_out = process_event_related(
            row, context, property_mappings, all_created_individuals_by_uid,
            equipment_ind=equipment_ind,
            line_ind=line_ind,
            material_ind=material_ind, # Pass context
            request_ind=request_ind, # Pass context
            pass_num=1,
            row_num=row_num  # Pass the actual row number explicitly
        )
        # TKT-002: Store row data with event-related individuals
        for entity_type, entity_ind in event_related_inds.items():
            created_inds_this_row[entity_type] = entity_ind
            context.store_individual_data(entity_ind, row)
            
        if event_context_out: 
            event_context = event_context_out
            # TKT-003: Validate event has correct resource type association
            event_ind, resource_ind, resource_type = event_context
            if equipment_type != resource_type:
                row_proc_logger.warning(f"Row {row_num} - TKT-003: EQUIPMENT_TYPE '{equipment_type}' does not match linked resource type '{resource_type}'. Event linking may be incorrect.")
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
    
    # TKT-005: Removed the redundant Equipment -> EquipmentClass linking logic
    # This relationship is properly handled during the initial population in Pass 1
    # by the process_equipment_and_class function (in equipment.py) which establishes 
    # memberOfClass links during the initial creation phase in the section labeled 
    # "TKT-005: EXPLICIT EQUIPMENT TO CLASS LINKING" (around line 476).
    # The post-processing step was redundant and logs showed it was finding 
    # 0 individuals needing linking.
    log.info("TKT-005: Skipping Equipment.memberOfClass structural relationships (handled in Pass 1 via process_equipment_and_class)")
    
    # Process Equipment -> ProductionLine relationships
    if "Equipment" in property_mappings and "object_properties" in property_mappings["Equipment"]:
        log.info("Processing Equipment.isPartOfProductionLine structural relationships...")
        
        # Get all Equipment individuals
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
                
                # TKT-010: Check for both column and target_link_context in the mapping
                line_id_column = eq_line_mapping.get("column")
                target_link_context = eq_line_mapping.get("target_link_context")
                
                # Method 1: Link via column value (original implementation)
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
                    
                    # Link equipment to lines using column values
                    for eq_ind in equipment_individuals:
                        # TKT-002: Use the get_individual_data method to retrieve stored data for equipment
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
                                # TKT-002: Use context.set_prop to ensure property usage is tracked
                                context.set_prop(eq_ind, "isPartOfProductionLine", line_ind)
                                context.set_prop(line_ind, "hasEquipmentPart", eq_ind)
                                links_created += 1
                                equipment_line_links += 1
                                log.debug(f"Linked Equipment {eq_ind.name} to Line {line_ind.name} via isPartOfProductionLine/hasEquipmentPart (column approach)")
                                
                                # Record the link type for statistics
                                links_by_type["Equipment->Line"] = links_by_type.get("Equipment->Line", 0) + 1
                
                # Method 2: TKT-010 - Link via target_link_context (new implementation)
                elif target_link_context:
                    log.info(f"TKT-010: Using target_link_context '{target_link_context}' for isPartOfProductionLine relationships")
                    
                    # For each equipment, find and link to the appropriate line using associated data
                    for eq_ind in equipment_individuals:
                        # Get the stored data for this equipment
                        eq_data = context.get_individual_data(eq_ind) or {}
                        
                        # Use the target_link_context to determine which line this equipment belongs to
                        # For example, if target_link_context is "ProductionLine", we need to find the line
                        # that this equipment should be linked to based on associated data
                        
                        # Approach 1: Direct column lookup for line ID if available (e.g., LINE_NAME)
                        candidate_line = None
                        
                        # Check for a stored "associatedLineId" property on equipment (may have been set during population)
                        if hasattr(eq_ind, "associatedLineId") and getattr(eq_ind, "associatedLineId"):
                            line_identifier = getattr(eq_ind, "associatedLineId")
                            if isinstance(line_identifier, list) and line_identifier:
                                line_identifier = line_identifier[0]
                            
                            # Find matching line by lineId
                            for line_ind in line_individuals:
                                if hasattr(line_ind, "lineId") and getattr(line_ind, "lineId"):
                                    line_id = getattr(line_ind, "lineId")
                                    if isinstance(line_id, list) and line_id:
                                        line_id = line_id[0]
                                    
                                    if str(line_id) == str(line_identifier):
                                        candidate_line = line_ind
                                        log.debug(f"TKT-010: Found line {line_ind.name} with ID {line_id} matching equipment's associatedLineId {line_identifier}")
                                        break
                        
                        # Approach 2: Check for LINE_NAME in stored equipment data
                        if not candidate_line and "LINE_NAME" in eq_data:
                            line_name_value = eq_data.get("LINE_NAME")
                            if line_name_value:
                                for line_ind in line_individuals:
                                    if hasattr(line_ind, "lineId") and getattr(line_ind, "lineId"):
                                        line_id = getattr(line_ind, "lineId")
                                        if isinstance(line_id, list) and line_id:
                                            line_id = line_id[0]
                                        
                                        if str(line_id) == str(line_name_value):
                                            candidate_line = line_ind
                                            log.debug(f"TKT-010: Found line {line_ind.name} with ID {line_id} matching equipment's LINE_NAME {line_name_value}")
                                            break
                        
                        # If we found a candidate line, create the link
                        if candidate_line:
                            # Check if the equipment is already linked to this line
                            current_line = getattr(eq_ind, is_part_of_line_prop.python_name, None)
                            equipment_already_linked = False
                            
                            if current_line:
                                if isinstance(current_line, list):
                                    equipment_already_linked = candidate_line in current_line
                                else:
                                    equipment_already_linked = current_line == candidate_line
                            
                            if not equipment_already_linked:
                                # Create bidirectional links
                                context.set_prop(eq_ind, "isPartOfProductionLine", candidate_line)
                                context.set_prop(candidate_line, "hasEquipmentPart", eq_ind)
                                links_created += 1
                                equipment_line_links += 1
                                log.info(f"TKT-010: Linked Equipment {eq_ind.name} to Line {candidate_line.name} via isPartOfProductionLine/hasEquipmentPart (context approach)")
                                
                                # Record the link type for statistics
                                links_by_type["Equipment->Line (Context)"] = links_by_type.get("Equipment->Line (Context)", 0) + 1
                        else:
                            log.debug(f"TKT-010: Could not find appropriate line for equipment {eq_ind.name} using context approach")
                
                else:
                    log.warning(f"TKT-010: No column or target_link_context specified for isPartOfProductionLine property mapping. Cannot link equipment to lines.")
                
                log.info(f"Created {equipment_line_links} Equipment-Line links")
    
    # TKT-002: Generate property usage report after all structural relationships are processed
    log.info("TKT-002: Generating property usage report")
    context.log_property_usage_report()
    
    # Log summary of links created
    for link_type, count in links_by_type.items():
        log.info(f"Created {count} {link_type} structural links")
    
    log.info(f"Post-processing complete: Created {links_created} structural links in total")
    return links_created 