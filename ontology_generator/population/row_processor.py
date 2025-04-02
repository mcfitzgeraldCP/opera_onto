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
        if event_context_out: event_context = event_context_out

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
            # The column that contains the Line ID for Equipment
            line_id_column = eq_line_mapping.get("column")
            
            if line_id_column:
                # First, build a lookup map for lines by their ID
                lines_by_id = {}
                line_id_prop = "lineId" # Property name expected to hold the ID value
                for line_ind in line_individuals:
                    # Get the line's ID value from its properties
                    if hasattr(line_ind, line_id_prop) and getattr(line_ind, line_id_prop):
                        line_id = getattr(line_ind, line_id_prop)
                        lines_by_id[str(line_id)] = line_ind
                
                log.info(f"Found {len(lines_by_id)} ProductionLine individuals with IDs")
                
                # Track Equipment individuals that need linking
                equipment_to_link = []
                for eq_ind in equipment_individuals:
                    # Check if this Equipment already has a line link
                    if hasattr(eq_ind, "isPartOfProductionLine") and eq_ind.isPartOfProductionLine:
                        continue  # Already linked
                    
                    # We need to determine which line this equipment should be linked to
                    # This requires knowing the line_id value from when the Equipment was created
                    # Ideally this would be stored in a property in the Equipment
                    equipment_to_link.append(eq_ind)
                
                log.info(f"Found {len(equipment_to_link)} Equipment individuals needing line links")
                
                # To find the line ID for an equipment, we could:
                # 1. Look for a property like "associatedLineId" in the Equipment (if it was added in Pass 1)
                # 2. Use a naming convention in the Equipment name/ID
                # 3. Use a more complex attribute analysis based on your data
                
                # For this simplified implementation, we'll try:
                # 1. Check if Equipment has a property holding the line ID
                # 2. Extract from Equipment name if it follows the naming pattern
                for eq_ind in equipment_to_link:
                    line_ind = None
                    line_id = None
                    
                    # Try method 1: Check if Equipment has a property like "associatedLineId"
                    if hasattr(eq_ind, "associatedLineId") and getattr(eq_ind, "associatedLineId"):
                        line_id = str(getattr(eq_ind, "associatedLineId"))
                        line_ind = lines_by_id.get(line_id)
                    
                    # Try method 2: Check if we can extract line ID from Equipment name/ID
                    if not line_ind and hasattr(eq_ind, "equipmentId"):
                        eq_id = getattr(eq_ind, "equipmentId")
                        # Try matching line IDs against equipment ID (assuming naming like "LINE1-EQ123")
                        for line_id, line in lines_by_id.items():
                            if line_id in str(eq_id):
                                line_ind = line
                                break
                    
                    # Try method 3: Look for most likely line based on other attributes
                    # (Custom logic based on your specific data model)
                    
                    # Set the bidirectional relationship if we found a match
                    if line_ind:
                        context.set_prop(eq_ind, "isPartOfProductionLine", line_ind)
                        context.set_prop(line_ind, "hasEquipmentPart", eq_ind)
                        links_created += 1
                        links_by_type["Equipment.isPartOfProductionLine"] = links_by_type.get("Equipment.isPartOfProductionLine", 0) + 1
                        log.debug(f"Linked Equipment {eq_ind.name} to ProductionLine {line_ind.name}")
    
    # Process Equipment -> EquipmentClass relationships
    if "Equipment" in property_mappings and "object_properties" in property_mappings["Equipment"]:
        log.info("Processing Equipment.memberOfClass structural relationships...")
        
        # Get all Equipment individuals
        equipment_individuals = [
            ind for uid, ind in all_created_individuals_by_uid.items() 
            if uid[0] == "Equipment"
        ]
        
        # Get all EquipmentClass individuals
        class_individuals = [
            ind for uid, ind in all_created_individuals_by_uid.items() 
            if uid[0] == "EquipmentClass"
        ]
        
        # Get the memberOfClass property mapping  
        member_class_mapping = property_mappings["Equipment"]["object_properties"].get("memberOfClass")
        
        if member_class_mapping and equipment_individuals and class_individuals:
            # Build a lookup map for equipment classes by their ID or name
            classes_by_id = {}
            classes_by_name = {}
            
            for class_ind in class_individuals:
                # By ID
                if hasattr(class_ind, "equipmentClassId") and getattr(class_ind, "equipmentClassId"):
                    class_id = str(getattr(class_ind, "equipmentClassId"))
                    classes_by_id[class_id] = class_ind
                
                # By name (from property or from individual name)
                if hasattr(class_ind, "equipmentClassName") and getattr(class_ind, "equipmentClassName"):
                    class_name = str(getattr(class_ind, "equipmentClassName"))
                    classes_by_name[class_name] = class_ind
                elif hasattr(class_ind, "name"):
                    name_parts = class_ind.name.split('_')
                    if len(name_parts) > 1:
                        classes_by_name[name_parts[-1]] = class_ind
            
            log.info(f"Found {len(classes_by_id)} EquipmentClass individuals with IDs and {len(classes_by_name)} with names")
            
            # Track Equipment individuals that need class linking
            equipment_to_link = []
            for eq_ind in equipment_individuals:
                # Check if this Equipment already has a class link
                if hasattr(eq_ind, "memberOfClass") and eq_ind.memberOfClass:
                    continue  # Already linked
                equipment_to_link.append(eq_ind)
            
            log.info(f"Found {len(equipment_to_link)} Equipment individuals needing class links")
            
            for eq_ind in equipment_to_link:
                class_ind = None
                
                # Try to determine class from Equipment properties or name
                if hasattr(eq_ind, "equipmentType") and getattr(eq_ind, "equipmentType"):
                    eq_type = str(getattr(eq_ind, "equipmentType"))
                    # Try exact match on ID then name
                    class_ind = classes_by_id.get(eq_type) or classes_by_name.get(eq_type)
                    
                    # Try fuzzy matching if needed
                    if not class_ind:
                        for cls_name, cls_ind in classes_by_name.items():
                            if cls_name.lower() in eq_type.lower() or eq_type.lower() in cls_name.lower():
                                class_ind = cls_ind
                                break
                
                # Set the relationship if we found a match
                if class_ind:
                    context.set_prop(eq_ind, "memberOfClass", class_ind)
                    links_created += 1
                    links_by_type["Equipment.memberOfClass"] = links_by_type.get("Equipment.memberOfClass", 0) + 1
                    log.debug(f"Linked Equipment {eq_ind.name} to EquipmentClass {class_ind.name}")
    
    # Log summary of created links
    log.info(f"Structural relationship post-processing complete. Created {links_created} links.")
    for rel_type, count in links_by_type.items():
        log.info(f"  • {rel_type}: {count} links")
    
    return links_created 