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
    if all_created_individuals_by_uid is None: return None # Error logged upstream

    cls_Shift = context.get_class("Shift")
    if not cls_Shift: return None

    shift_id_map = property_mappings['Shift'].get('data_properties', {}).get('shiftId')
    start_time_map = property_mappings['Shift'].get('data_properties', {}).get('shiftStartTime')
    end_time_map = property_mappings['Shift'].get('data_properties', {}).get('shiftEndTime')

    if not shift_id_map or not shift_id_map.get('column'):
        pop_logger.warning("Mapping for Shift.shiftId column not found. Skipping shift.")
        return None
    # Start/end times are crucial for identification/labeling if ID isn't unique
    if not start_time_map or not start_time_map.get('column') or not end_time_map or not end_time_map.get('column'):
         pop_logger.warning("Mapping for Shift start/end time columns not found. Skipping shift.")
         return None

    shift_id_col = shift_id_map['column']
    shift_id = safe_cast(row.get(shift_id_col), str)
    start_time_str = safe_cast(row.get(start_time_map['column']), str)
    end_time_str = safe_cast(row.get(end_time_map['column']), str)

    if not shift_id or not start_time_str:
        pop_logger.debug(f"Missing shift ID ('{shift_id_col}') or start time ('{start_time_map['column']}') in row. Skipping shift.")
        return None

    # Create a unique base name, e.g., ShiftID_StartTime
    shift_unique_base = f"{shift_id}_{start_time_str}"
    shift_labels = [shift_id, f"{start_time_str} to {end_time_str or '?'}"]

    shift_ind = get_or_create_individual(cls_Shift, shift_unique_base, context.onto, all_created_individuals_by_uid, add_labels=shift_labels)

    if shift_ind and pass_num == 1:
        apply_data_property_mappings(shift_ind, property_mappings["Shift"], row, context, "Shift", pop_logger)
        # Potential: Calculate duration if mapping exists? Or leave to reasoner/post-processing?
        # duration_map = property_mappings['Shift'].get('data_properties', {}).get('shiftDurationMinutes')
        # if duration_map ... calculate ... context.set_prop(...)

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
    if all_created_individuals_by_uid is None: return None

    cls_State = context.get_class("OperationalState")
    if not cls_State: return None

    state_desc_map = property_mappings['OperationalState'].get('data_properties', {}).get('stateDescription')
    if not state_desc_map or not state_desc_map.get('column'):
        pop_logger.warning("Mapping for OperationalState.stateDescription column not found. Skipping state.")
        return None

    state_desc_col = state_desc_map['column']
    state_desc = safe_cast(row.get(state_desc_col), str)
    if not state_desc:
        pop_logger.debug(f"No State Description found in column '{state_desc_col}'. Skipping state.")
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
    if all_created_individuals_by_uid is None: return None

    cls_Reason = context.get_class("OperationalReason")
    if not cls_Reason: return None

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
        pop_logger.warning("Mapping for OperationalReason description column (reasonDescription or altReasonDescription) not found. Skipping reason.")
        return None

    if not reason_desc:
        pop_logger.debug(f"No Reason Description found in column '{reason_desc_col}'. Skipping reason.")
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
    pass_num: int = 1
) -> Optional[Thing]:
    """
    Processes TimeInterval from a row (Pass 1: Create/Data Props).
    Requires startTime mapping. endTime mapping is needed for the property but not strictly for creation.
    Uses resource_base_id and row_num for unique naming.
    
    If startTime is missing, creates a robust fallback name using resource ID and row number.
    """
    if not property_mappings or "TimeInterval" not in property_mappings:
        pop_logger.debug("Property mappings for 'TimeInterval' not provided. Skipping interval processing.")
        return None
    if all_created_individuals_by_uid is None: return None

    cls_Interval = context.get_class("TimeInterval")
    if not cls_Interval: return None

    start_map = property_mappings['TimeInterval'].get('data_properties', {}).get('startTime')
    end_map = property_mappings['TimeInterval'].get('data_properties', {}).get('endTime')

    if not start_map or not start_map.get('column'):
        pop_logger.warning("Mapping for TimeInterval.startTime column not found. Using fallback naming scheme.")
        has_start_mapping = False
    else:
        has_start_mapping = True

    # Extract available time data with validation
    start_col = start_map.get('column') if start_map else None
    end_col = end_map.get('column') if end_map else None
    
    start_time_str = None
    end_time_str = None
    valid_start_time = False
    
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
        if not end_time_str:
            pop_logger.debug(f"Row {row_num}: No endTime value in column '{end_col}'.")

    # Create a robust unique base name
    if valid_start_time:
        # Create a safe start time string for naming
        safe_start_time_str = start_time_str.replace(":", "").replace("+", "plus").replace(" ", "T")
        interval_unique_base = f"Interval_{resource_base_id}_{safe_start_time_str}_Row{row_num}"
        end_label_part = f"to {end_time_str}" if end_time_str else "(No End Time)"
        interval_labels = [f"Interval for {resource_base_id} starting {start_time_str} {end_label_part}"]
    else:
        # Robust fallback naming when no valid start time exists
        interval_unique_base = f"Interval_{resource_base_id}_Row{row_num}"
        interval_labels = [f"Interval for {resource_base_id} (Row {row_num}, StartTime Missing)"]
        pop_logger.warning(f"Row {row_num}: Using fallback naming scheme for TimeInterval: '{interval_unique_base}' due to missing startTime")

    # Create the TimeInterval individual with the determined name
    interval_ind = get_or_create_individual(cls_Interval, interval_unique_base, context.onto, all_created_individuals_by_uid, add_labels=interval_labels)

    if interval_ind and pass_num == 1:
        # Apply all data properties from mappings (will include startTime/endTime if they exist)
        apply_data_property_mappings(interval_ind, property_mappings["TimeInterval"], row, context, "TimeInterval", pop_logger)
        
        # Verify the startTime property was actually set
        has_start_prop = hasattr(interval_ind, 'startTime') and interval_ind.startTime
        if not has_start_prop:
            pop_logger.warning(f"Row {row_num}: TimeInterval {interval_ind.name} created but startTime property not set. This may cause linking issues.")

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
    Processes EventRecord from a row (Pass 1: Create/Data Props).
    Links to other entities (State, Reason, Shift, Resource, etc.) are deferred to Pass 2.

    Uses hints like 'EQUIPMENT_TYPE' column to determine if it's a line or equipment event.
    Requires mappings for startTime, endTime (to identify interval).

    Returns:
        Tuple: (event_individual, event_context_for_linking)
               event_context_for_linking: (event_ind, primary_resource_ind, time_interval_ind, line_ind_for_context)
    """
    if not property_mappings or "EventRecord" not in property_mappings:
        pop_logger.debug("Property mappings for 'EventRecord' not provided. Skipping event record processing.")
        return None, None
    if all_created_individuals_by_uid is None: return None, None

    cls_Event = context.get_class("EventRecord")
    if not cls_Event: return None, None

    # --- Determine Primary Resource --- 
    # Use EQUIPMENT_TYPE column as a hint (based on linking log errors)
    resource_type_hint = row.get('EQUIPMENT_TYPE', 'Equipment').strip()
    primary_resource_ind = None
    resource_id_for_name = None

    if resource_type_hint == 'Line':
        if line_ind:
            primary_resource_ind = line_ind
            # Try to get a stable ID for the name
            resource_id_for_name = line_ind.lineId[0] if hasattr(line_ind, 'lineId') and line_ind.lineId else line_ind.name
            pop_logger.debug(f"Identified event for Line: {resource_id_for_name}")
        else:
            pop_logger.warning(f"Row indicates a Line event based on '{resource_type_hint}', but no Line individual found. Skipping event.")
            return None, None
    # Default to Equipment if hint is 'Equipment' or unknown/fallback
    else: 
        if resource_type_hint != 'Equipment':
             pop_logger.debug(f"Unknown resource type hint '{resource_type_hint}' in row. Defaulting event resource to Equipment.")
        
        if equipment_ind:
            primary_resource_ind = equipment_ind
            # Try to get a stable ID for the name
            resource_id_for_name = equipment_ind.equipmentId[0] if hasattr(equipment_ind, 'equipmentId') and equipment_ind.equipmentId else equipment_ind.name
            pop_logger.debug(f"Identified event for Equipment: {resource_id_for_name}")
        else:
            # If it should be an equipment event but no equipment_ind, we cannot proceed
            pop_logger.warning(f"Row indicates an Equipment event (type: '{resource_type_hint}'), but no Equipment individual found. Skipping event.")
            return None, None

    # --- Check Dependencies (Time Interval) --- 
    if not time_interval_ind:
         pop_logger.warning("TimeInterval individual not provided for event record. Skipping event.")
         return None, None

    # Extract start time from the interval for the unique name
    start_time_str = None
    # Retrieve start time value directly from the interval individual for naming consistency
    start_time_val = getattr(time_interval_ind, 'startTime', None)
    if isinstance(start_time_val, datetime):
        start_time_str = start_time_val.isoformat()
    elif start_time_val: # Handle if it's stored as string or other type
         start_time_str = str(start_time_val)
    # Fallback if startTime property is missing on the interval
    elif interval_ind := all_created_individuals_by_uid.get(("TimeInterval", time_interval_ind.name)): # Check registry
         start_time_val = getattr(interval_ind, 'startTime', None)
         if isinstance(start_time_val, datetime): start_time_str = start_time_val.isoformat()
         elif start_time_val: start_time_str = str(start_time_val)

    # If start_time_str is *still* None after checks, we cannot reliably name the event
    if start_time_str is None:
        pop_logger.warning(f"Cannot find startTime property value on TimeInterval {time_interval_ind.name}. Using fallback event naming based on interval name.")
        # Use the interval's name itself as part of the event name base
        start_time_str = time_interval_ind.name # Fallback to interval name

    # --- Create Unique ID & Labels --- 
    # Ensure resource_id_for_name was set
    if not resource_id_for_name:
         pop_logger.error(f"Could not determine a valid ID for the primary resource ('{resource_type_hint}'). Skipping event.")
         return None, None

    # Use row_num in the unique base name for robustness
    event_unique_base = f"Event_{resource_id_for_name}_{start_time_str}_{row_num}"
    event_labels = [f"Event for {resource_id_for_name} at {start_time_str} (Row: {row_num})"]
    # Add state/reason descriptions to label if available?
    if state_ind and hasattr(state_ind, 'stateDescription') and state_ind.stateDescription:
        # Handle potential locstr or list
        state_desc = state_ind.stateDescription[0] if isinstance(state_ind.stateDescription, list) else state_ind.stateDescription
        event_labels.append(f"State: {state_desc}")
    if reason_ind and hasattr(reason_ind, 'reasonDescription') and reason_ind.reasonDescription:
        reason_desc = reason_ind.reasonDescription[0] if isinstance(reason_ind.reasonDescription, list) else reason_ind.reasonDescription
        event_labels.append(f"Reason: {reason_desc}")

    # --- Create Individual --- 
    event_ind = get_or_create_individual(cls_Event, event_unique_base, context.onto, all_created_individuals_by_uid, add_labels=event_labels)

    # --- Apply Data Properties & Prepare Context --- 
    event_context_out = None
    if event_ind and pass_num == 1:
        # Apply data properties
        apply_data_property_mappings(event_ind, property_mappings["EventRecord"], row, context, "EventRecord", pop_logger)

        # FIX: Directly link the resource right away during creation (involvesResource property)
        if primary_resource_ind:
            involves_resource_prop = context.get_prop("involvesResource")
            if involves_resource_prop:
                context.set_prop(event_ind, "involvesResource", primary_resource_ind)
                pop_logger.debug(f"Linked event {event_ind.name} directly to resource {primary_resource_ind.name} via involvesResource")

        # Prepare context for later linking steps if needed
        # Use the *determined* primary_resource_ind as the 2nd element
        # The 4th element (line_ind) provides context for where equipment events occurred
        event_context_out = (event_ind, primary_resource_ind, time_interval_ind, line_ind)

    return event_ind, event_context_out


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
    row_num: int = -1  # Add row_num parameter with default value
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

    # Pass the actual row number to process_time_interval
    time_interval_ind = process_time_interval(row, context, resource_base_id, actual_row_num, property_mappings, all_created_individuals_by_uid, pass_num)
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
