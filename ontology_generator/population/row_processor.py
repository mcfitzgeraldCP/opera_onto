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
        equipment_ind, eq_class_ind, eq_class_info_out = process_equipment_and_class(
             row, context, property_mappings, all_created_individuals_by_uid, line_ind, pass_num=1
        )
        if equipment_ind: created_inds_this_row["Equipment"] = equipment_ind
        if eq_class_ind: created_inds_this_row["EquipmentClass"] = eq_class_ind
        if eq_class_info_out: eq_class_info = eq_class_info_out

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
                apply_object_property_mappings(
                    individual,
                    property_mappings[entity_type],
                    row,
                    context,
                    entity_type,
                    row_proc_logger,
                    linking_context,
                    individuals_in_row
                )

        row_proc_logger.debug(f"Row {row_num} - Pass 2 End.")

    except Exception as e:
        row_proc_logger.error(f"Row {row_num} - Pass 2: Critical error during linking: {e}", exc_info=True)
        success = False
    finally:
        # Clean up temporary key
        if 'row_num' in row: del row['row_num']

    return success 