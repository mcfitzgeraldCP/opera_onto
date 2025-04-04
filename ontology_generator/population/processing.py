"""
Module for processing individual data rows during ontology population.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from owlready2 import Thing, ThingClass

# Assuming PopulationContext is defined elsewhere and imported appropriately
from .core import PopulationContext
# Assuming processing functions are available
from .asset import process_asset_hierarchy, process_material, process_production_request
from .equipment import process_equipment
from .events import process_shift, process_state, process_reason, process_time_interval, process_event_record

# Use a logger specific to this module
proc_logger = logging.getLogger(__name__)

# Define a return type structure for clarity
RowProcessingResult = Tuple[
    bool,  # Success status
    Optional[Tuple[Thing, Thing, Thing, Thing]], # event_context: (event_ind, resource_ind, time_interval_ind, line_ind_associated)
    Optional[Tuple[str, Thing, Optional[int]]] # eq_class_info: (eq_class_name, eq_class_ind, position)
]

def process_single_data_row(row: Dict[str, Any],
                            row_num: int,
                            context: PopulationContext,
                            property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None) \
                            -> RowProcessingResult:
    """
    Processes a single data row to create ontology individuals and relationships.

    Args:
        row: The data dictionary for the current row.
        row_num: The original row number (for logging).
        context: The PopulationContext object.
        property_mappings: The parsed property mappings.

    Returns:
        A tuple containing:
        - bool: True if processing was successful, False otherwise.
        - Optional[Tuple]: Event context tuple (event_ind, resource_ind, time_interval_ind, line_ind_associated)
                         if an event was successfully created and linked, otherwise None.
        - Optional[Tuple]: Equipment class info (name, individual, position) if relevant,
                         otherwise None.
    """
    proc_logger.debug(f"--- Processing Row {row_num} ---")
    try:
        # 1. Process Asset Hierarchy -> plant, area, pcell, line individuals
        plant_ind, area_ind, pcell_ind, line_ind = process_asset_hierarchy(row, context, property_mappings)
        if not plant_ind:  # Plant is essential
            raise ValueError("Failed to establish Plant individual, cannot proceed with row.")

        # 2. Determine Resource (Line or Equipment) for the Event
        eq_type = row.get('EQUIPMENT_TYPE', '')
        resource_individual: Optional[Thing] = None
        resource_base_id: Optional[str] = None  # For naming related individuals
        equipment_ind: Optional[Thing] = None
        eq_class_ind: Optional[ThingClass] = None
        eq_class_name: Optional[str] = None
        eq_class_pos: Optional[int] = None
        eq_class_info_result: Optional[Tuple[str, Thing, Optional[int]]] = None

        if eq_type == 'Line' and line_ind:
            resource_individual = line_ind
            resource_base_id = line_ind.name
            proc_logger.debug(f"Row {row_num}: Identified as Line record for: {line_ind.name}")

        elif eq_type == 'Equipment':
            equipment_ind, eq_class_ind, eq_class_name = process_equipment(row, context, line_ind, property_mappings)
            if equipment_ind:
                resource_individual = equipment_ind
                resource_base_id = f"Eq_{equipment_ind.name}"
                if eq_class_ind and eq_class_name:
                    # Attempt to get position; getattr returns None if attribute doesn't exist
                    pos_val = getattr(eq_class_ind, "defaultSequencePosition", None)
                    # Ensure position is an integer if found
                    eq_class_pos = int(pos_val) if isinstance(pos_val, (int, float, str)) and str(pos_val).isdigit() else None
                    eq_class_info_result = (eq_class_name, eq_class_ind, eq_class_pos)
                    proc_logger.debug(f"Row {row_num}: Processed Equipment {equipment_ind.name} of class {eq_class_name} (Pos: {eq_class_pos})")
            else:
                 proc_logger.warning(f"Row {row_num}: Identified as Equipment record, but failed to process Equipment individual. Event linkages might be incomplete.")

        else:
            proc_logger.warning(f"Row {row_num}: Could not determine resource. EQUIPMENT_TYPE='{eq_type}', EQUIPMENT_ID='{row.get('EQUIPMENT_ID')}', LINE_NAME='{row.get('LINE_NAME')}'. Event linkages might be incomplete.")

        if not resource_individual:
            proc_logger.error(f"Row {row_num}: No valid resource (Line or Equipment) identified. Cannot link event record correctly.")
            resource_base_id = f"UnknownResource_Row{row_num}" # Fallback for naming
            # Continue processing other parts, but event linking will fail later

        # 3. Process Material
        material_ind = process_material(row, context, property_mappings)

        # 4. Process Production Request
        request_ind = process_production_request(row, context, property_mappings)

        # 5. Process Shift
        shift_ind = process_shift(
            row=row, 
            context=context, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=None,  # We don't have this in this context
            pass_num=1
        )

        # 6. Process State & Reason (now as separate functions)
        state_ind = process_state(
            row=row, 
            context=context, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=None,  # We don't have this in this context
            pass_num=1
        )
        reason_ind = process_reason(
            row=row, 
            context=context, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=None,  # We don't have this in this context
            pass_num=1
        )

        # 7. Process Time Interval
        time_interval_ind = process_time_interval(
            row=row, 
            context=context, 
            resource_base_id=resource_base_id, 
            row_num=row_num, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=None,  # We don't have this in this context
            pass_num=1
        )

        # 8. Process Event Record and Links
        event_ind: Optional[Thing] = None
        event_context_result: Optional[Tuple[Thing, Thing, Thing, Thing]] = None
        if resource_individual and time_interval_ind: # Need resource and interval for meaningful event
            event_ind, event_context_tuple = process_event_record(
                row=row,
                context=context,
                property_mappings=property_mappings,
                all_created_individuals_by_uid=None,  # We don't have this in this context
                time_interval_ind=time_interval_ind,
                shift_ind=shift_ind,
                state_ind=state_ind,
                reason_ind=reason_ind,
                equipment_ind=equipment_ind,
                line_ind=line_ind,
                material_ind=material_ind,
                request_ind=request_ind,
                pass_num=1,
                row_num=row_num
            )
            if not event_ind:
                raise ValueError("Failed to create EventRecord individual.")
            else:
                # Extract resource_ind from the event context tuple returned by process_event_record
                resource_ind_from_tuple = event_context_tuple[1] if event_context_tuple and len(event_context_tuple) > 1 else resource_individual
                
                # Determine associated line for linking context
                associated_line_ind: Optional[Thing] = None
                prod_line_class = context.get_class("ProductionLine")
                equipment_class = context.get_class("Equipment")
                part_of_prop = context.get_prop("isPartOfProductionLine")

                if prod_line_class and isinstance(resource_ind_from_tuple, prod_line_class):
                    associated_line_ind = resource_ind_from_tuple
                elif equipment_class and part_of_prop and isinstance(resource_ind_from_tuple, equipment_class):
                    # Safely access potentially multi-valued property
                    line_val = getattr(resource_ind_from_tuple, part_of_prop.python_name, None)
                    if isinstance(line_val, list) and line_val:
                        associated_line_ind = line_val[0] # Take first if multiple
                    elif line_val and not isinstance(line_val, list):
                        associated_line_ind = line_val # Assign if single value

                # Check if associated_line_ind is indeed a ProductionLine instance
                if prod_line_class and isinstance(associated_line_ind, prod_line_class):
                    event_context_result = (event_ind, resource_ind_from_tuple, time_interval_ind, associated_line_ind)
                    proc_logger.debug(f"Row {row_num}: Stored context for Event {event_ind.name} (Resource: {resource_ind_from_tuple.name}, Line: {associated_line_ind.name})")
                else:
                    proc_logger.warning(f"Row {row_num}: Could not determine associated ProductionLine for Event {event_ind.name} (Resource: {resource_ind_from_tuple.name}). Skipping context for isPartOfLineEvent linking.")
        elif not resource_individual:
             proc_logger.warning(f"Row {row_num}: Skipping EventRecord creation as no valid resource individual was found.")
        elif not time_interval_ind:
             proc_logger.warning(f"Row {row_num}: Skipping EventRecord creation as no valid time interval individual was found or created.")

        # Return success and any gathered context/info
        return True, event_context_result, eq_class_info_result

    except (KeyError, ValueError, TypeError, AttributeError) as specific_err:
        # Log specific errors with traceback
        proc_logger.error(f"Specific error processing data row {row_num} (Type: {type(specific_err).__name__}): {row if len(str(row)) < 500 else str(row)[:500] + '...'}", exc_info=True)
        return False, None, None # Indicate failure
    except Exception as e:
        # Log unexpected errors with traceback
        proc_logger.error(f"An unexpected error processing data row {row_num}: {row if len(str(row)) < 500 else str(row)[:500] + '...'}", exc_info=True)
        return False, None, None # Indicate failure