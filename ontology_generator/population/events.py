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
    property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    all_created_individuals_by_uid: IndividualRegistry = None,
    pass_num: int = 1
) -> Optional[Thing]:
    """
    Processes TimeInterval from a row (Pass 1: Create/Data Props).
    Requires startTime and endTime mappings.
    """
    if not property_mappings or "TimeInterval" not in property_mappings:
        pop_logger.debug("Property mappings for 'TimeInterval' not provided. Skipping interval processing.")
        return None
    if all_created_individuals_by_uid is None: return None

    cls_Interval = context.get_class("TimeInterval")
    if not cls_Interval: return None

    start_map = property_mappings['TimeInterval'].get('data_properties', {}).get('startTime')
    end_map = property_mappings['TimeInterval'].get('data_properties', {}).get('endTime')

    if not start_map or not start_map.get('column') or not end_map or not end_map.get('column'):
        pop_logger.warning("Mapping for TimeInterval start/end time columns not found. Skipping interval.")
        return None

    start_col = start_map['column']
    end_col = end_map['column']
    start_time_str = safe_cast(row.get(start_col), str)
    end_time_str = safe_cast(row.get(end_col), str)

    if not start_time_str or not end_time_str:
        pop_logger.debug(f"Missing start ('{start_col}') or end ('{end_col}') time in row. Skipping interval.")
        return None

    # Create unique base name, e.g., StartTime_EndTime
    interval_unique_base = f"{start_time_str}_{end_time_str}"
    interval_labels = [f"{start_time_str} to {end_time_str}"]

    interval_ind = get_or_create_individual(cls_Interval, interval_unique_base, context.onto, all_created_individuals_by_uid, add_labels=interval_labels)

    if interval_ind and pass_num == 1:
        apply_data_property_mappings(interval_ind, property_mappings["TimeInterval"], row, context, "TimeInterval", pop_logger)
        # Maybe calculate duration?

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
    pass_num: int = 1
) -> Tuple[Optional[Thing], Optional[Tuple]]:
    """
    Processes EventRecord from a row (Pass 1: Create/Data Props).
    Links to other entities (State, Reason, Shift, Resource, etc.) are deferred to Pass 2.

    Requires mappings for startTime, endTime (to identify interval) and involvedResource (Equipment ID).

    Returns:
        Tuple: (event_individual, event_context_for_linking)
               event_context_for_linking: (event_ind, resource_ind, time_interval_ind, line_ind)
    """
    if not property_mappings or "EventRecord" not in property_mappings:
        pop_logger.debug("Property mappings for 'EventRecord' not provided. Skipping event record processing.")
        return None, None
    if all_created_individuals_by_uid is None: return None, None

    cls_Event = context.get_class("EventRecord")
    if not cls_Event: return None, None

    # Essential info for unique ID: Resource (Equipment) ID and Start Time
    # We use the equipment *individual* passed in, assuming it was processed first.
    # Get start time from the TimeInterval individual, assuming it was processed first.
    if not equipment_ind:
        pop_logger.warning("Equipment individual not provided for event record. Cannot create unique event ID. Skipping event.")
        return None, None
    if not time_interval_ind:
         pop_logger.warning("TimeInterval individual not provided for event record. Cannot create unique event ID. Skipping event.")
         return None, None

    # Extract equipment ID and start time for the unique name
    equip_id = None
    if hasattr(equipment_ind, 'equipmentId') and equipment_ind.equipmentId:
        equip_id = equipment_ind.equipmentId[0] # Assumes functional
    else:
        # Fallback: try to parse from name? Risky.
        pop_logger.warning(f"Cannot find equipmentId on provided Equipment individual {equipment_ind.name}. Attempting to use name as fallback ID.")
        equip_id = equipment_ind.name # Use individual name as last resort

    start_time_str = None
    if hasattr(time_interval_ind, 'startTime') and time_interval_ind.startTime:
        start_time_str = time_interval_ind.startTime[0] # Assumes functional
    else:
        pop_logger.warning(f"Cannot find startTime on provided TimeInterval individual {time_interval_ind.name}. Cannot create unique event ID. Skipping event.")
        return None, None

    if not equip_id or not start_time_str:
         pop_logger.error(f"Could not determine Equipment ID or Start Time for event involving {equipment_ind.name}. Skipping event.")
         return None, None

    event_unique_base = f"Event_{equip_id}_{start_time_str}"
    event_labels = [f"Event for {equip_id} at {start_time_str}"]
    # Add state/reason descriptions to label if available?
    if state_ind and hasattr(state_ind, 'stateDescription') and state_ind.stateDescription:
        event_labels.append(f"State: {state_ind.stateDescription[0]}")
    if reason_ind and hasattr(reason_ind, 'reasonDescription') and reason_ind.reasonDescription:
        event_labels.append(f"Reason: {reason_ind.reasonDescription[0]}")

    event_ind = get_or_create_individual(cls_Event, event_unique_base, context.onto, all_created_individuals_by_uid, add_labels=event_labels)

    event_context_out = None
    if event_ind and pass_num == 1:
        # Apply data properties
        apply_data_property_mappings(event_ind, property_mappings["EventRecord"], row, context, "EventRecord", pop_logger)

        # DEFER ALL OBJECT PROPERTY LINKS to Pass 2:
        # - occursDuring -> time_interval_ind
        # - duringShift -> shift_ind
        # - eventHasState -> state_ind
        # - eventHasReason -> reason_ind
        # - involvesResource -> equipment_ind
        # - usesMaterial -> material_ind (if mapping exists)
        # - associatedWithProductionRequest -> request_ind (if mapping exists)
        # - isPartOfLineEvent (Handled later by _link_equipment_events)
        # - hasDetailedEquipmentEvent (Handled later?)
        # - performedBy (Person) (Handled later?)

        # Prepare context for later linking steps if needed
        event_context_out = (event_ind, equipment_ind, time_interval_ind, line_ind)

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
    pass_num: int = 1
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

    # Process in dependency order (roughly)
    shift_ind = process_shift(row, context, property_mappings, all_created_individuals_by_uid, pass_num)
    if shift_ind: created_inds["Shift"] = shift_ind

    time_interval_ind = process_time_interval(row, context, property_mappings, all_created_individuals_by_uid, pass_num)
    if time_interval_ind: created_inds["TimeInterval"] = time_interval_ind

    state_ind = process_state(row, context, property_mappings, all_created_individuals_by_uid, pass_num)
    if state_ind: created_inds["OperationalState"] = state_ind

    reason_ind = process_reason(row, context, property_mappings, all_created_individuals_by_uid, pass_num)
    if reason_ind: created_inds["OperationalReason"] = reason_ind

    # Process the main EventRecord, passing the individuals created above
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
        pass_num=pass_num
    )
    if event_ind: 
        created_inds["EventRecord"] = event_ind
        event_context_out = event_context_tuple # Capture context from successful event creation

    # Only return individuals created/found in this scope
    return created_inds, event_context_out
