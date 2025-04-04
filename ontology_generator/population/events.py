"""
Events population module for the ontology generator.

This module provides functions for processing event-related data.
"""
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

from owlready2 import Thing, locstr

from ontology_generator.utils.logging import pop_logger
from ontology_generator.utils.types import safe_cast
from ontology_generator.population.core import (
    PopulationContext, get_or_create_individual, apply_data_property_mappings
)
from ontology_generator.config import COUNTRY_TO_LANGUAGE, DEFAULT_LANGUAGE
from ontology_generator.population.linking import link_equipment_events_to_line_events

# Type Alias for registry
IndividualRegistry = Dict[Tuple[str, str], Thing] # Key: (entity_type_str, unique_id_str), Value: Individual Object
RowIndividuals = Dict[str, Thing] # Key: entity_type_str, Value: Individual Object for this row

def process_shift(
    row: Dict[str, Any],
    context: PopulationContext,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None,
    pass_num: int = 1
) -> Optional[Thing]:
    """
    Processes Shift from a row (Pass 1: Create/Data Props).
    Requires shiftId, startTime, endTime mappings.
    """
    if not property_mappings or "Shift" not in property_mappings:
        pop_logger.debug("Property mappings for 'Shift' not provided. Skipping shift processing.")
        return None
    if all_created_individuals_by_uid is None:
        pop_logger.error("Individual registry not provided to process_shift. Skipping.")
        return None

    cls_Shift = context.get_class("Shift")
    if not cls_Shift:
        pop_logger.error("Shift class not found in ontology. Skipping shift processing.")
        return None

    # Check for required property mappings
    shift_id_map = property_mappings['Shift'].get('data_properties', {}).get('shiftId')
    start_time_map = property_mappings['Shift'].get('data_properties', {}).get('shiftStartTime')
    end_time_map = property_mappings['Shift'].get('data_properties', {}).get('shiftEndTime')

    if not shift_id_map or not shift_id_map.get('column'):
        pop_logger.warning("Required property mapping 'shiftId' not found. Skipping shift creation.")
        return None
    # Start/end times are crucial for identification/labeling if ID isn't unique
    if not start_time_map or not start_time_map.get('column'):
         pop_logger.warning("Required property mapping 'shiftStartTime' not found. Skipping shift creation.")
         return None
    if not end_time_map or not end_time_map.get('column'):
         pop_logger.warning("Required property mapping 'shiftEndTime' not found. Skipping shift creation.")
         return None

    shift_id_col = shift_id_map['column']
    shift_id = safe_cast(row.get(shift_id_col), str)
    start_time_str = safe_cast(row.get(start_time_map['column']), str)
    end_time_str = safe_cast(row.get(end_time_map['column']), str)

    if not shift_id:
        pop_logger.debug(f"Missing shift ID in column '{shift_id_col}'. Skipping shift creation.")
        return None
    if not start_time_str:
        pop_logger.debug(f"Missing shift start time in column '{start_time_map['column']}'. Skipping shift creation.")
        return None

    # Create a unique base name, e.g., ShiftID_StartTime
    shift_unique_base = f"{shift_id}_{start_time_str}"
    shift_labels = [shift_id, f"{start_time_str} to {end_time_str or '?'}"]

    shift_ind = get_or_create_individual(cls_Shift, shift_unique_base, context.onto, all_created_individuals_by_uid, add_labels=shift_labels)

    if shift_ind and pass_num == 1:
        apply_data_property_mappings(shift_ind, property_mappings["Shift"], row, context, "Shift", pop_logger)

    return shift_ind

def process_state(
    row: Dict[str, Any],
    context: PopulationContext,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None,
    pass_num: int = 1
) -> Optional[Thing]:
    """
    Processes OperationalState from a row (Pass 1: Create/Data Props).
    Requires stateDescription mapping.
    """
    if not property_mappings or "OperationalState" not in property_mappings:
        pop_logger.debug("Property mappings for 'OperationalState' not provided. Skipping state processing.")
        return None
    if all_created_individuals_by_uid is None:
        pop_logger.error("Individual registry not provided to process_state. Skipping.")
        return None

    cls_State = context.get_class("OperationalState")
    if not cls_State:
        pop_logger.error("OperationalState class not found in ontology. Skipping state processing.")
        return None

    # Check for required property mapping: stateDescription
    state_desc_map = property_mappings['OperationalState'].get('data_properties', {}).get('stateDescription')
    if not state_desc_map or not state_desc_map.get('column'):
        pop_logger.warning("Required property mapping 'stateDescription' not found. Skipping state creation.")
        return None

    state_desc_col = state_desc_map['column']
    state_desc = safe_cast(row.get(state_desc_col), str)
    if not state_desc:
        pop_logger.debug(f"Missing state description in column '{state_desc_col}'. Skipping state creation.")
        return None

    # Use description as the base name (assuming descriptions are reasonably unique states)
    state_unique_base = state_desc
    state_labels = [state_desc]

    state_ind = get_or_create_individual(cls_State, state_unique_base, context.onto, all_created_individuals_by_uid, add_labels=state_labels)

    if state_ind and pass_num == 1:
        apply_data_property_mappings(state_ind, property_mappings["OperationalState"], row, context, "OperationalState", pop_logger)

    return state_ind

def process_reason(
    row: Dict[str, Any],
    context: PopulationContext,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None,
    pass_num: int = 1
) -> Optional[Thing]:
    """
    Processes OperationalReason from a row (Pass 1: Create/Data Props).
    Requires reasonDescription or altReasonDescription mapping.
    """
    if not property_mappings or "OperationalReason" not in property_mappings:
        pop_logger.debug("Property mappings for 'OperationalReason' not provided. Skipping reason processing.")
        return None
    if all_created_individuals_by_uid is None:
        pop_logger.error("Individual registry not provided to process_reason. Skipping.")
        return None

    cls_Reason = context.get_class("OperationalReason")
    if not cls_Reason:
        pop_logger.error("OperationalReason class not found in ontology. Skipping reason processing.")
        return None

    # Check for required property mappings: reasonDescription or altReasonDescription
    reason_desc_map = property_mappings['OperationalReason'].get('data_properties', {}).get('reasonDescription')
    alt_reason_desc_map = property_mappings['OperationalReason'].get('data_properties', {}).get('altReasonDescription')

    reason_desc_col = None
    reason_desc = None

    if reason_desc_map and reason_desc_map.get('column'):
        reason_desc_col = reason_desc_map['column']
        reason_desc = safe_cast(row.get(reason_desc_col), str)
    elif alt_reason_desc_map and alt_reason_desc_map.get('column'):
        reason_desc_col = alt_reason_desc_map['column']
        reason_desc = safe_cast(row.get(reason_desc_col), str)
        pop_logger.debug(f"Using altReasonDescription column '{reason_desc_col}' for reason.")
    else:
        pop_logger.warning("Required property mapping for reason description (reasonDescription or altReasonDescription) not found. Skipping reason creation.")
        return None

    if not reason_desc:
        pop_logger.debug(f"Missing reason description in column '{reason_desc_col}'. Skipping reason creation.")
        return None

    # Use description as the base name
    reason_unique_base = reason_desc
    reason_labels = [reason_desc]

    reason_ind = get_or_create_individual(cls_Reason, reason_unique_base, context.onto, all_created_individuals_by_uid, add_labels=reason_labels)

    if reason_ind and pass_num == 1:
        apply_data_property_mappings(reason_ind, property_mappings["OperationalReason"], row, context, "OperationalReason", pop_logger)

    return reason_ind

def process_time_interval(
    row: Dict[str, Any],
    context: PopulationContext,
    resource_base_id: str,
    row_num: int,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None,
    pass_num: int = 1,
    infer_missing_end_time: bool = False,  # New parameter to optionally infer missing end times
    default_duration_hours: int = 2  # Default duration for inferring end times
) -> Optional[Thing]:
    """
    Processes TimeInterval from a row (Pass 1: Create/Data Props).
    Requires startTime mapping. endTime mapping is needed for the property but not strictly for creation.
    Uses resource_base_id and row_num for unique naming.
    
    If startTime is missing, creates a robust fallback name using resource ID and row number.
    
    Args:
        row: The data row
        context: The population context
        resource_base_id: The base ID for the resource (equipment/line)
        row_num: The row number for unique naming
        property_mappings: The property mappings
        all_created_individuals_by_uid: The registry of created individuals
        pass_num: The current pass number
        infer_missing_end_time: If True, infer end times for intervals with missing end times
        default_duration_hours: Default duration in hours to use for inferring end times
        
    Returns:
        The created interval individual
    """
    if not property_mappings or "TimeInterval" not in property_mappings:
        pop_logger.debug("Property mappings for 'TimeInterval' not provided. Skipping interval processing.")
        return None
    if all_created_individuals_by_uid is None:
        pop_logger.error("Individual registry not provided to process_time_interval. Skipping.")
        return None

    cls_Interval = context.get_class("TimeInterval")
    if not cls_Interval:
        pop_logger.error("TimeInterval class not found in ontology. Skipping interval processing.")
        return None

    # Check for required property mappings: startTime (required) and endTime (optional but important)
    start_map = property_mappings['TimeInterval'].get('data_properties', {}).get('startTime')
    end_map = property_mappings['TimeInterval'].get('data_properties', {}).get('endTime')

    if not start_map or not start_map.get('column'):
        pop_logger.warning("Required property mapping 'startTime' not found. Using fallback naming scheme.")
        has_start_mapping = False
    else:
        has_start_mapping = True

    # Extract available time data with validation
    start_col = start_map.get('column') if start_map else None
    end_col = end_map.get('column') if end_map else None
    
    start_time_str = None
    end_time_str = None
    valid_start_time = False
    valid_end_time = False
    
    # Try to extract startTime value (even if we'll use a fallback name, we want the data property)
    if has_start_mapping and start_col:
        start_time_str = safe_cast(row.get(start_col), str)
        if start_time_str:
            valid_start_time = True
        else:
            pop_logger.warning(f"Row {row_num}: Missing startTime value from column '{start_col}'.")
    
    # Try to extract endTime if available
    if end_col:
        end_time_str = safe_cast(row.get(end_col), str)
        if end_time_str:
            valid_end_time = True
        else:
            pop_logger.debug(f"Row {row_num}: No endTime value in column '{end_col}'.")
            if infer_missing_end_time and valid_start_time:
                # Logic to infer end time would go here if we needed it
                # For now, we're just focusing on property checks
                pass

    # Create a robust unique base name
    if valid_start_time:
        # Create a safe start time string for naming
        safe_start_time_str = start_time_str.replace(":", "").replace("+", "plus").replace(" ", "T")
        interval_unique_base = f"Interval_{resource_base_id}_{safe_start_time_str}_Row{row_num}"
        end_label_part = f"to {end_time_str}" if valid_end_time else "(No End Time)"
        interval_labels = [f"Interval for {resource_base_id} starting {start_time_str} {end_label_part}"]
    else:
        # Fallback when no valid start time, use row-based approach only
        interval_unique_base = f"Interval_{resource_base_id}_Row{row_num}"
        interval_labels = [f"Interval for {resource_base_id} (Row {row_num})"]
        pop_logger.warning(f"Using fallback naming for time interval '{interval_unique_base}' due to missing start time.")

    # Create or retrieve the interval individual
    interval_ind = get_or_create_individual(cls_Interval, interval_unique_base, context.onto, all_created_individuals_by_uid, add_labels=interval_labels)

    if interval_ind and pass_num == 1:
        apply_data_property_mappings(interval_ind, property_mappings["TimeInterval"], row, context, "TimeInterval", pop_logger)

    return interval_ind

def process_event_record(
    row: Dict[str, Any],
    context: PopulationContext,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None,
    # Pass individuals created earlier in the row processing for context if needed
    time_interval_ind: Optional[Thing] = None,
    shift_ind: Optional[Thing] = None,
    state_ind: Optional[Thing] = None,
    reason_ind: Optional[Thing] = None,
    equipment_ind: Optional[Thing] = None, # The primary resource involved
    line_ind: Optional[Thing] = None, # The line context
    material_ind: Optional[Thing] = None, # Optional context
    request_ind: Optional[Thing] = None, # Optional context
    pass_num: int = 1,
    row_num: int = -1
) -> Tuple[Optional[Thing], Optional[Tuple]]:
    """
    Processes EventRecord from a row (Pass 1: Create/Data Props and critical links).
    
    Critical context for individual creation comes from relationships with other individuals:
    - time_interval_ind: When the event occurred
    - equipment_ind OR line_ind: Resource involved (at least one should be present)
    - state_ind: The operational state of the resource
    - reason_ind: Optional reason for the state

    Returns:
        Tuple: (event_ind, event_tuple)
               - event_ind: The created event individual
               - event_tuple: Context tuple for post-processing if needed
    """
    if not property_mappings or "EventRecord" not in property_mappings:
        pop_logger.debug("Property mappings for 'EventRecord' not provided. Skipping event processing.")
        return None, None
    if all_created_individuals_by_uid is None:
        pop_logger.error("Individual registry not provided to process_event_record. Skipping.")
        return None, None

    cls_Event = context.get_class("EventRecord")
    if not cls_Event:
        pop_logger.error("EventRecord class not found in ontology. Skipping event processing.")
        return None, None

    # Validate required context individuals for creating meaningful events
    if not time_interval_ind:
        pop_logger.warning(f"Row {row_num}: Missing time interval individual for event. Skipping event creation.")
        return None, None
    if not state_ind:
        pop_logger.warning(f"Row {row_num}: Missing state individual for event. Skipping event creation.")
        return None, None
    if not (equipment_ind or line_ind):
        pop_logger.warning(f"Row {row_num}: Missing both equipment and line individuals for event. Need at least one resource. Skipping event creation.")
        return None, None

    # Check EQUIPMENT_TYPE column to determine the correct resource to link
    equipment_type = row.get('EQUIPMENT_TYPE', '').strip()
    
    # Determine the main resource involved based on EQUIPMENT_TYPE
    if equipment_type == 'Line':
        if not line_ind:
            pop_logger.warning(f"Row {row_num}: EQUIPMENT_TYPE is 'Line' but no line_ind was provided. Cannot link event to line resource.")
            return None, None
        resource_ind = line_ind
        resource_type = "Line"
    elif equipment_type == 'Equipment':
        if not equipment_ind:
            pop_logger.warning(f"Row {row_num}: EQUIPMENT_TYPE is 'Equipment' but no equipment_ind was provided. Cannot link event to equipment resource.")
            return None, None
        resource_ind = equipment_ind
        resource_type = "Equipment"
    else:
        # Fallback to previous logic for backwards compatibility
        pop_logger.warning(f"Row {row_num}: Unknown EQUIPMENT_TYPE '{equipment_type}'. Falling back to equipment_ind if available, otherwise line_ind.")
        resource_ind = equipment_ind if equipment_ind else line_ind
        resource_type = "Equipment" if equipment_ind else "Line"
    
    resource_id = None
    
    # Extract resource ID with property existence check
    if resource_type == "Equipment":
        # Check for equipmentId property on the individual
        equipment_id_prop = context.get_prop("equipmentId")
        if equipment_id_prop and hasattr(resource_ind, "equipmentId"):
            resource_id = resource_ind.equipmentId
        else:
            # Fall back to name-based extraction
            if hasattr(resource_ind, "name"):
                resource_id = resource_ind.name.split("_")[-1]  # Extract from individual name
            else:
                resource_id = f"Unknown{row_num}"
                pop_logger.warning(f"Row {row_num}: Could not determine equipment ID for event. Using fallback ID '{resource_id}'.")
    else:  # Line
        # Check for lineId property on the individual
        line_id_prop = context.get_prop("lineId")
        if line_id_prop and hasattr(resource_ind, "lineId"):
            resource_id = resource_ind.lineId
        else:
            # Fall back to name-based extraction
            if hasattr(resource_ind, "name"):
                resource_id = resource_ind.name.split("_")[-1]  # Extract from individual name
            else:
                resource_id = f"UnknownLine{row_num}"
                pop_logger.warning(f"Row {row_num}: Could not determine line ID for event. Using fallback ID '{resource_id}'.")

    # Extract start time for uniqueness if available
    start_time_str = "Unknown"
    start_time_prop = context.get_prop("startTime")
    if start_time_prop and hasattr(time_interval_ind, "startTime"):
        start_time_val = time_interval_ind.startTime
        start_time_str = str(start_time_val).replace(":", "").replace(" ", "T").replace("+", "plus")
    
    # Extract state description for labeling if available
    state_desc = "Unknown State"
    state_desc_prop = context.get_prop("stateDescription")
    if state_desc_prop and hasattr(state_ind, "stateDescription"):
        state_desc = state_ind.stateDescription
    
    # Create a unique ID for the event
    event_unique_base = f"Event_{resource_id}_{start_time_str}_Row{row_num}"
    
    # Create descriptive labels
    event_labels = []
    # Primary user-friendly label based on resource and state
    event_labels.append(f"{resource_type} {resource_id} {state_desc} at {start_time_str}")
    
    # Add reason if available with property existence check
    if reason_ind:
        reason_desc_prop = context.get_prop("reasonDescription")
        reason_desc = None
        if reason_desc_prop and hasattr(reason_ind, "reasonDescription"):
            reason_desc = reason_ind.reasonDescription
            if reason_desc:
                event_labels.append(f"Reason: {reason_desc}")
        
        alt_reason_desc_prop = context.get_prop("altReasonDescription")
        if not reason_desc and alt_reason_desc_prop and hasattr(reason_ind, "altReasonDescription"):
            alt_reason_desc = reason_ind.altReasonDescription
            if alt_reason_desc:
                event_labels.append(f"Reason: {alt_reason_desc}")
    
    # Create or retrieve EventRecord individual
    event_ind = get_or_create_individual(cls_Event, event_unique_base, context.onto, all_created_individuals_by_uid, add_labels=event_labels)

    if event_ind and pass_num == 1:
        # Apply standard data property mappings
        apply_data_property_mappings(event_ind, property_mappings["EventRecord"], row, context, "EventRecord", pop_logger)
        
        # --- CRITICAL OBJECT PROPERTY LINKING FOR EVENT CONTEXT ---
        
        # 1. Link to TimeInterval (when the event occurred) - critical
        # Check for occursDuring property existence
        occurs_during_prop = context.get_prop("occursDuring")
        if occurs_during_prop:
            context.set_prop(event_ind, "occursDuring", time_interval_ind)
        else:
            pop_logger.warning(f"Row {row_num}: Required property 'occursDuring' not found. Cannot link event to time interval.")
        
        # 2. Link to OperationalState - critical
        # Check for hasOperationalState property existence
        has_state_prop = context.get_prop("eventHasState")
        if has_state_prop:
            context.set_prop(event_ind, "eventHasState", state_ind)
        else:
            pop_logger.warning(f"Row {row_num}: Required property 'eventHasState' not found. Cannot link event to state.")
        
        # 3. Link to OperationalReason if available
        if reason_ind:
            # Check for hasOperationalReason property existence
            has_reason_prop = context.get_prop("eventHasReason")
            if has_reason_prop:
                context.set_prop(event_ind, "eventHasReason", reason_ind)
            else:
                pop_logger.warning(f"Row {row_num}: Required property 'eventHasReason' not found. Cannot link event to reason.")
        
        # 4. Link to primary resource (Equipment or ProductionLine) - critical
        # Check for involvesResource property existence
        involves_resource_prop = context.get_prop("involvesResource")
        if involves_resource_prop:
            context.set_prop(event_ind, "involvesResource", resource_ind)
        else:
            pop_logger.warning(f"Row {row_num}: Required property 'involvesResource' not found. Cannot link event to resource.")
        
        # 5. Link to Shift if available
        if shift_ind:
            # Check for occursInShift property existence
            occurs_in_shift_prop = context.get_prop("duringShift")
            if occurs_in_shift_prop:
                context.set_prop(event_ind, "duringShift", shift_ind)
            else:
                pop_logger.warning(f"Row {row_num}: Property 'duringShift' not found. Cannot link event to shift.")
        
        # 6. Link to Material if available and context equipment/line supports it
        if material_ind:
            # Check for involvesMaterial property existence
            involves_material_prop = context.get_prop("usesMaterial")
            if involves_material_prop:
                context.set_prop(event_ind, "usesMaterial", material_ind)
            else:
                pop_logger.warning(f"Row {row_num}: Property 'usesMaterial' not found. Cannot link event to material.")
        
        # 7. Link to ProductionRequest if available
        if request_ind:
            # Check for involvesRequest property existence
            involves_request_prop = context.get_prop("forRequest")
            if involves_request_prop:
                context.set_prop(event_ind, "forRequest", request_ind)
            else:
                pop_logger.warning(f"Row {row_num}: Property 'forRequest' not found. Cannot link event to production request.")
    
    # Create event context tuple for post-processing
    event_context = (event_ind, resource_ind, resource_type) if event_ind else None
    
    return event_ind, event_context

def process_event_related(
    row: Dict[str, Any],
    context: PopulationContext,
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None,
    # Pass required context individuals identified earlier in the row
    equipment_ind: Optional[Thing] = None,
    line_ind: Optional[Thing] = None,
    material_ind: Optional[Thing] = None,
    request_ind: Optional[Thing] = None,
    pass_num: int = 1,
    row_num: int = -1,  # Add row_num parameter with default value
    infer_missing_end_times: bool = True,  # Control whether to infer missing end times
    default_duration_hours: int = 2  # Default duration for inferred end times
) -> Tuple[RowIndividuals, Optional[Tuple]]:
    """
    Orchestrates the processing of all event-related individuals for a row in a given pass.

    Pass 1: Creates Shift, TimeInterval, State, Reason, EventRecord. Applies data props.
            Returns created individuals and event context tuple.
    Pass 2: (No actions needed here - linking done externally via apply_object_property_mappings)

    Args:
        row: Data row.
        context: Population context.
        property_mappings: Property mappings.
        all_created_individuals_by_uid: Central individual registry.
        equipment_ind: Equipment individual for this event context.
        line_ind: Line individual for this event context.
        material_ind: Optional material individual for context.
        request_ind: Optional production request for context.
        pass_num: Current population pass.
        row_num: Original row number from the source data for robust naming.
        infer_missing_end_times: If True, infer missing end times for time intervals.
        default_duration_hours: Default duration in hours to use for inferring end times.

    Returns:
        Tuple: (created_individuals_dict, event_context_tuple)
                - created_individuals_dict: Dict of event-related individuals created/found.
                - event_context_tuple: Context for later linking steps (from process_event_record).
    """
    created_inds: RowIndividuals = {}
    event_context_out = None

    if all_created_individuals_by_uid is None:
        pop_logger.error("Individual registry not provided to process_event_related. Skipping.")
        return {}, None

    # Get the actual row number from the row dict if available
    actual_row_num = row.get('row_num', row_num)
    if actual_row_num == -1:
        pop_logger.warning(f"No valid row_num provided or found in row. Using fallback value. This may cause naming issues.")

    # Determine resource_base_id needed for interval processing
    # This duplicates some logic from process_event_record but is needed early for interval naming
    resource_base_id = None
    resource_type_hint = row.get('EQUIPMENT_TYPE', 'Equipment').strip()

    # Verify that both the required individuals (line_ind or equipment_ind) are available based on EQUIPMENT_TYPE
    if resource_type_hint == 'Line' and not line_ind:
        pop_logger.warning(f"Row {actual_row_num}: EQUIPMENT_TYPE is 'Line' but no line_ind was provided. Event processing may fail.")
    elif resource_type_hint == 'Equipment' and not equipment_ind:
        pop_logger.warning(f"Row {actual_row_num}: EQUIPMENT_TYPE is 'Equipment' but no equipment_ind was provided. Event processing may fail.")
        
    if resource_type_hint == 'Line':
        if line_ind:
            resource_base_id = line_ind.lineId[0] if hasattr(line_ind, 'lineId') and line_ind.lineId else line_ind.name
    else: # Default to Equipment
        if equipment_ind:
            resource_base_id = equipment_ind.equipmentId[0] if hasattr(equipment_ind, 'equipmentId') and equipment_ind.equipmentId else equipment_ind.name

    if not resource_base_id:
         pop_logger.warning(f"Row {actual_row_num}: Could not determine resource_base_id early for interval naming (TypeHint: {resource_type_hint}, Line: {line_ind}, Eq: {equipment_ind}). Using fallback.")
         resource_base_id = f"UnknownResource_{hash(str(row))}" # Example: Use row hash for fallback uniqueness

    # Process in dependency order (roughly)
    shift_ind = process_shift(row, context, property_mappings, all_created_individuals_by_uid, pass_num)
    if shift_ind: created_inds["Shift"] = shift_ind

    # Pass the actual row number and inference parameters to process_time_interval
    time_interval_ind = process_time_interval(
        row, context, resource_base_id, actual_row_num, property_mappings, all_created_individuals_by_uid, pass_num,
        infer_missing_end_time=infer_missing_end_times, default_duration_hours=default_duration_hours
    )
    if time_interval_ind: created_inds["TimeInterval"] = time_interval_ind

    state_ind = process_state(row, context, property_mappings, all_created_individuals_by_uid, pass_num)
    if state_ind: created_inds["OperationalState"] = state_ind

    reason_ind = process_reason(row, context, property_mappings, all_created_individuals_by_uid, pass_num)
    if reason_ind: created_inds["OperationalReason"] = reason_ind

    # --- Process the main EventRecord --- 
    # Pass the actual row number to process_event_record
    event_ind, event_context_tuple = process_event_record(
        row, context, property_mappings, all_created_individuals_by_uid,
        time_interval_ind=time_interval_ind,
        shift_ind=shift_ind,
        state_ind=state_ind,
        reason_ind=reason_ind,
        equipment_ind=equipment_ind,
        line_ind=line_ind,
        material_ind=material_ind,
        request_ind=request_ind,
        pass_num=pass_num,
        row_num=actual_row_num  # Pass the actual row number
    )
    if event_ind:
        created_inds["EventRecord"] = event_ind
        event_context_out = event_context_tuple # Capture context from successful event creation

    # Only return individuals created/found in this scope
    return created_inds, event_context_out
