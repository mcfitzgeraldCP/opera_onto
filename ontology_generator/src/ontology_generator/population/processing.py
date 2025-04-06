"""
Module for processing individual data rows during ontology population.
"""
import logging
from typing import Any, Dict, Optional, Tuple, List, Set

from owlready2 import Thing, ThingClass, Ontology, PropertyClass

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
    Optional[Tuple[Thing, Thing, str, Thing]], # event_context: (event_ind, resource_ind, resource_type, line_ind_associated)
    Optional[Tuple[str, Thing, Optional[int]]] # eq_class_info: (eq_class_name, eq_class_ind, position)
]

def process_single_data_row(row: Dict[str, Any],
                            row_num: int,
                            context: PopulationContext,
                            property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
                            all_created_individuals_by_uid: Dict[Tuple[str, str], Thing] = None) \
                            -> RowProcessingResult:
    """
    Processes a single data row to create ontology individuals and relationships.

    Args:
        row: The data dictionary for the current row.
        row_num: The original row number (for logging).
        context: The PopulationContext object.
        property_mappings: The parsed property mappings.
        all_created_individuals_by_uid: Registry of created individuals for reuse.

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
        plant_ind, area_ind, pcell_ind, line_ind = process_asset_hierarchy(
            row=row, 
            context=context, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=all_created_individuals_by_uid
        )
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
            equipment_ind, eq_class_ind, eq_class_name = process_equipment(
                row=row, 
                context=context, 
                line_ind=line_ind, 
                property_mappings=property_mappings
            )
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
        material_ind = process_material(
            row=row, 
            context=context, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=all_created_individuals_by_uid
        )

        # 4. Process Production Request
        request_ind = process_production_request(
            row=row, 
            context=context, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=all_created_individuals_by_uid
        )

        # 5. Process Shift
        shift_ind = process_shift(
            row=row, 
            context=context, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=all_created_individuals_by_uid,
            pass_num=1
        )

        # 6. Process State & Reason (now as separate functions)
        state_ind = process_state(
            row=row, 
            context=context, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=all_created_individuals_by_uid,
            pass_num=1
        )
        reason_ind = process_reason(
            row=row, 
            context=context, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=all_created_individuals_by_uid,
            pass_num=1
        )

        # 7. Process Time Interval
        time_interval_ind = process_time_interval(
            row=row, 
            context=context, 
            resource_base_id=resource_base_id, 
            row_num=row_num, 
            property_mappings=property_mappings,
            all_created_individuals_by_uid=all_created_individuals_by_uid,
            pass_num=1
        )

        # 8. Process Event Record and Links
        event_ind: Optional[Thing] = None
        event_context_result: Optional[Tuple[Thing, Thing, str, Thing]] = None
        if resource_individual and time_interval_ind: # Need resource and interval for meaningful event
            event_ind, event_context_tuple = process_event_record(
                row=row,
                context=context,
                property_mappings=property_mappings,
                all_created_individuals_by_uid=all_created_individuals_by_uid,
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
                    # Determine the resource type string (either "Line" or "Equipment")
                    resource_type_str = "Line" if isinstance(resource_ind_from_tuple, prod_line_class) else "Equipment"
                    
                    # Create the tuple with the correct format: (event_ind, resource_ind, resource_type_str, associated_line_ind)
                    event_context_result = (event_ind, resource_ind_from_tuple, resource_type_str, associated_line_ind)
                    proc_logger.debug(f"Row {row_num}: Stored context for Event {event_ind.name} (Resource: {resource_ind_from_tuple.name}, Type: {resource_type_str}, Line: {associated_line_ind.name})")
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

def populate_ontology_from_data(onto: Ontology,
                                data_rows: List[Dict[str, Any]],
                                defined_classes: Dict[str, ThingClass],
                                defined_properties: Dict[str, PropertyClass],
                                property_is_functional: Dict[str, bool],
                                specification: List[Dict[str, str]],
                                property_mappings: Dict[str, Dict[str, Dict[str, Any]]] = None
                              ) -> Tuple[int, Dict[str, ThingClass], Dict[str, int], List[Tuple[Thing, Thing, str, Thing]], Dict[Tuple[str, str], Thing], PopulationContext]:
    """
    Populates the ontology from data rows, creating individuals and establishing links.
    
    Args:
        onto: The ontology to populate
        data_rows: The parsed data rows
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties
        property_is_functional: Dictionary indicating which properties are functional
        specification: The parsed specification
        property_mappings: The parsed property mappings
    
    Returns:
        Tuple containing:
        - failed_rows_count: Number of rows that failed to process
        - created_eq_classes: Dictionary of equipment classes created
        - eq_class_positions: Dictionary of equipment class positions
        - created_events_context: List of tuples (event_ind, resource_ind, resource_type, line_ind_associated)
                              where resource_type is a string ("Line" or "Equipment")
        - all_created_individuals_by_uid: Registry of all created individuals
        - population_context: The PopulationContext used during population (for property reporting)
    """
    # Create the PopulationContext
    context = PopulationContext(onto, defined_classes, defined_properties, property_is_functional)
    proc_logger.info(f"Created population context with {len(defined_classes)} classes and {len(defined_properties)} properties")
    
    # Validate property mappings
    if not property_mappings:
        proc_logger.error("No property mappings provided. Population may fail or be incomplete.")
        # Continue anyway with empty mappings
        property_mappings = {}
    
    # Initialize counters and containers
    failed_rows_count = 0
    total_rows = len(data_rows)
    created_events_context: List[Tuple[Thing, Thing, str, Thing]] = []
    created_eq_classes: Dict[str, ThingClass] = {}  # Key: class name, Value: class individual
    eq_class_positions: Dict[str, int] = {}  # Key: class name, Value: sequence position
    all_created_individuals_by_uid: Dict[Tuple[str, str], Thing] = {}  # Registry for get_or_create lookups
    
    # Process each data row
    for index, row in enumerate(data_rows):
        row_num = index + 1  # 1-indexed for user-friendly logging
        
        # Process row and gather context/info
        success, event_context, eq_class_info = process_single_data_row(
            row, row_num, context, property_mappings, all_created_individuals_by_uid
        )
        
        if not success:
            failed_rows_count += 1
            continue  # Skip to next row
        
        # Store event context if available
        if event_context:
            created_events_context.append(event_context)
        
        # Store equipment class info if available
        if eq_class_info:
            eq_class_name, eq_class_ind, position = eq_class_info
            created_eq_classes[eq_class_name] = eq_class_ind
            if position is not None:
                eq_class_positions[eq_class_name] = position
    
    # Log statistics
    proc_logger.info(f"Ontology population complete: Processed {total_rows} rows with {failed_rows_count} failures.")
    proc_logger.info(f"Created {len(created_eq_classes)} unique equipment classes")
    proc_logger.info(f"Collected {len(created_events_context)} event contexts for linking")
    
    # TKT-002: Return the PopulationContext for property usage reporting
    return failed_rows_count, created_eq_classes, eq_class_positions, created_events_context, all_created_individuals_by_uid, context