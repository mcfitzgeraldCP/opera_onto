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
    PopulationContext, get_or_create_individual, apply_property_mappings,
    set_prop_if_col_exists
)
from ontology_generator.config import COUNTRY_TO_LANGUAGE, DEFAULT_LANGUAGE

def process_shift(row: Dict[str, Any], 
                 context: PopulationContext, 
                 property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
                ) -> Optional[Thing]:
    """
    Processes Shift from a row.
    
    Args:
        row: The data row
        context: The population context
        property_mappings: Optional property mappings dictionary
        
    Returns:
        The Shift individual or None
    """
    cls_Shift = context.get_class("Shift")
    if not cls_Shift: 
        return None

    shift_name = safe_cast(row.get('SHIFT_NAME'), str)
    if not shift_name:
        pop_logger.debug("No SHIFT_NAME in row, skipping shift creation.")
        return None

    shift_labels = [shift_name]
    shift_ind = get_or_create_individual(cls_Shift, shift_name, context.onto, add_labels=shift_labels)
    if not shift_ind: 
        return None

    # Check if we can use dynamic property mappings
    if property_mappings and "Shift" in property_mappings:
        shift_mappings = property_mappings["Shift"]
        
        # Process data properties from mappings
        populated_props = 0
        for prop_name, prop_info in shift_mappings.get("data_properties", {}).items():
            col_name = prop_info.get("column")
            data_type = prop_info.get("data_type")
            
            if col_name and data_type:
                # Special check for shiftId to avoid overwriting
                if prop_name == "shiftId" and getattr(shift_ind, "shiftId", None) == shift_name:
                    pop_logger.debug(f"Shift.shiftId already set to {shift_name}, skipping")
                    continue
                    
                # For other properties, check if they're already set
                if prop_name != "shiftId" and getattr(shift_ind, prop_name, None) is not None:
                    pop_logger.debug(f"Shift.{prop_name} already set, skipping")
                    continue
                    
                # Apply the property mapping
                apply_property_mappings(shift_ind, {"data_properties": {prop_name: prop_info}}, row, context, "Shift", pop_logger)
                populated_props += 1
        
        pop_logger.debug(f"Populated {populated_props} properties for Shift from dynamic mappings")
    else:
        # Fallback to hardcoded property assignments
        pop_logger.debug("Using hardcoded property assignments for Shift (no dynamic mappings available)")
        # Populate shift details (Functional properties, assign only if needed/missing)
        # Check before setting to avoid redundant operations if individual already exists
        if getattr(shift_ind, "shiftId", None) != shift_name:
            context.set_prop_if_col_exists(shift_ind, "shiftId", 'SHIFT_NAME', row, safe_cast, str, pop_logger)
        if getattr(shift_ind, "shiftStartTime", None) is None:
            context.set_prop_if_col_exists(shift_ind, "shiftStartTime", 'SHIFT_START_DATE_LOC', row, safe_cast, datetime, pop_logger)
        if getattr(shift_ind, "shiftEndTime", None) is None:
            context.set_prop_if_col_exists(shift_ind, "shiftEndTime", 'SHIFT_END_DATE_LOC', row, safe_cast, datetime, pop_logger)
        if getattr(shift_ind, "shiftDurationMinutes", None) is None:
            context.set_prop_if_col_exists(shift_ind, "shiftDurationMinutes", 'SHIFT_DURATION_MIN', row, safe_cast, float, pop_logger)

    return shift_ind


def process_state_reason(row: Dict[str, Any], 
                         context: PopulationContext, 
                         property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
                        ) -> Tuple[Optional[Thing], Optional[Thing]]:
    """
    Processes OperationalState and OperationalReason from a row.
    
    Args:
        row: The data row
        context: The population context
        property_mappings: Optional property mappings dictionary
        
    Returns:
        A tuple of (state_individual, reason_individual)
    """
    cls_OperationalState = context.get_class("OperationalState")
    cls_OperationalReason = context.get_class("OperationalReason")
    if not cls_OperationalState or not cls_OperationalReason: 
        return None, None

    # OperationalState
    state_desc = safe_cast(row.get('UTIL_STATE_DESCRIPTION'), str)
    state_ind: Optional[Thing] = None
    if state_desc:
        state_labels = [state_desc]
        state_ind = get_or_create_individual(cls_OperationalState, state_desc, context.onto, add_labels=state_labels)
        if state_ind:
            # Check if we can use dynamic property mappings for state
            if property_mappings and "OperationalState" in property_mappings:
                state_mappings = property_mappings["OperationalState"]
                apply_property_mappings(state_ind, state_mappings, row, context, "OperationalState", pop_logger)
            else:
                # Fallback to hardcoded property assignments
                # Set description (Non-functional)
                context.set_prop_if_col_exists(state_ind, "stateDescription", 'UTIL_STATE_DESCRIPTION', row, safe_cast, str, pop_logger)
    else:
        pop_logger.debug("No UTIL_STATE_DESCRIPTION in row.")

    # OperationalReason
    reason_desc = safe_cast(row.get('UTIL_REASON_DESCRIPTION'), str)
    reason_ind: Optional[Thing] = None
    if reason_desc:
        reason_labels = [reason_desc]
        reason_ind = get_or_create_individual(cls_OperationalReason, reason_desc, context.onto, add_labels=reason_labels)
        if reason_ind:
            # Check if we can use dynamic property mappings for reason
            if property_mappings and "OperationalReason" in property_mappings:
                reason_mappings = property_mappings["OperationalReason"]
                
                # Process data properties from mappings
                for prop_name, prop_info in reason_mappings.get("data_properties", {}).items():
                    col_name = prop_info.get("column")
                    data_type = prop_info.get("data_type")
                    
                    if col_name and data_type:
                        # Special handling for alt reason description with language tag
                        if prop_name == "altReasonDescription" and data_type == "xsd:string (with lang tag)":
                            alt_reason = safe_cast(row.get(col_name), str)
                            if alt_reason:
                                plant_country = safe_cast(row.get('PLANT_COUNTRY_DESCRIPTION'), str)
                                lang_tag = COUNTRY_TO_LANGUAGE.get(plant_country, DEFAULT_LANGUAGE) if plant_country else DEFAULT_LANGUAGE
                                try:
                                    alt_reason_locstr = locstr(alt_reason, lang=lang_tag)
                                    context.set_prop(reason_ind, prop_name, alt_reason_locstr)
                                    pop_logger.debug(f"Set OperationalReason.{prop_name} with localized string '{alt_reason}'@{lang_tag}")
                                    continue
                                except Exception as e_loc:
                                    pop_logger.warning(f"Failed to create locstr for alt reason '{alt_reason}': {e_loc}. Storing as plain string.")
                                    # Continue to regular processing as fallback
                        
                        # For all other properties, use standard property mapping
                        apply_property_mappings(reason_ind, {"data_properties": {prop_name: prop_info}}, row, context, "OperationalReason", pop_logger)
                
                # Also process object properties
                if reason_mappings.get("object_properties"):
                    apply_property_mappings(reason_ind, {"object_properties": reason_mappings["object_properties"]}, row, context, "OperationalReason", pop_logger)
                    
                pop_logger.debug(f"Applied mappings for OperationalReason")
            else:
                # Fallback to hardcoded property assignments
                # Set description (Non-functional)
                context.set_prop_if_col_exists(reason_ind, "reasonDescription", 'UTIL_REASON_DESCRIPTION', row, safe_cast, str, pop_logger)

                # Handle AltReasonDescription with language tag (Non-functional)
                alt_reason = safe_cast(row.get('UTIL_ALT_LANGUAGE_REASON'), str)
                if alt_reason:
                    plant_country = safe_cast(row.get('PLANT_COUNTRY_DESCRIPTION'), str)
                    lang_tag = COUNTRY_TO_LANGUAGE.get(plant_country, DEFAULT_LANGUAGE) if plant_country else DEFAULT_LANGUAGE
                    try:
                        alt_reason_locstr = locstr(alt_reason, lang=lang_tag)
                        context.set_prop(reason_ind, "altReasonDescription", alt_reason_locstr)
                        pop_logger.debug(f"Added localized reason '{alt_reason}'@{lang_tag} to {reason_ind.name}")
                    except Exception as e_loc:
                        pop_logger.warning(f"Failed to create locstr for alt reason '{alt_reason}': {e_loc}. Storing as plain string.")
                        # Fallback to plain string if locstr fails or lang_tag is missing
                        context.set_prop(reason_ind, "altReasonDescription", alt_reason)

                # Other reason properties (Non-functional)
                context.set_prop_if_col_exists(reason_ind, "downtimeDriver", 'DOWNTIME_DRIVER', row, safe_cast, str, pop_logger)
                co_type = safe_cast(row.get('CO_TYPE'), str)
                context.set_prop_if_col_exists(reason_ind, "changeoverType", 'CO_TYPE', row, safe_cast, str, pop_logger)
    else:
        pop_logger.debug("No UTIL_REASON_DESCRIPTION in row.")

    return state_ind, reason_ind


def process_time_interval(row: Dict[str, Any], 
                          context: PopulationContext, 
                          resource_base_id: str, 
                          row_num: int,
                          property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
                         ) -> Optional[Thing]:
    """
    Processes TimeInterval from a row.
    
    Args:
        row: The data row
        context: The population context
        resource_base_id: The base ID of the associated resource
        row_num: The row number
        property_mappings: Optional property mappings dictionary
        
    Returns:
        The TimeInterval individual or None
    """
    cls_TimeInterval = context.get_class("TimeInterval")
    if not cls_TimeInterval: 
        return None

    start_time = safe_cast(row.get('JOB_START_TIME_LOC'), datetime)
    end_time = safe_cast(row.get('JOB_END_TIME_LOC'), datetime)

    if not start_time:
        pop_logger.warning(f"Row {row_num}: Missing JOB_START_TIME_LOC. Cannot create a unique TimeInterval based on start time. Attempting fallback naming.")
        # Fallback naming strategy - less ideal, relies on uniqueness of other fields for the row
        interval_base = f"Interval_{resource_base_id}_Row{row_num}"
        interval_labels = [f"Interval for {resource_base_id} (Row {row_num})"]
        # Proceed even without start time if necessary for the EventRecord
    else:
        # Create a unique TimeInterval using resource, start time, and row number
        start_time_str = start_time.strftime('%Y%m%dT%H%M%S%f')[:-3]  # Milliseconds precision
        interval_base = f"Interval_{resource_base_id}_{start_time_str}_{row_num}"
        interval_labels = [f"Interval for {resource_base_id} starting {start_time}"]

    time_interval_ind = get_or_create_individual(cls_TimeInterval, interval_base, context.onto, add_labels=interval_labels)
    if not time_interval_ind:
        pop_logger.error(f"Row {row_num}: Failed to create TimeInterval individual '{interval_base}'.")
        return None

    # Set TimeInterval properties (Functional)
    if start_time: 
        context.set_prop_if_col_exists(time_interval_ind, "startTime", 'JOB_START_TIME_LOC', row, safe_cast, datetime, pop_logger)
    if end_time: 
        context.set_prop_if_col_exists(time_interval_ind, "endTime", 'JOB_END_TIME_LOC', row, safe_cast, datetime, pop_logger)

    return time_interval_ind


def process_event_record(row: Dict[str, Any], 
                         context: PopulationContext,
                         resource_individual: Thing, 
                         resource_base_id: str, 
                         row_num: int,
                         request_ind: Optional[Thing], 
                         material_ind: Optional[Thing],
                         time_interval_ind: Optional[Thing], 
                         shift_ind: Optional[Thing],
                         state_ind: Optional[Thing], 
                         reason_ind: Optional[Thing],
                         property_mappings: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
                        ) -> Optional[Thing]:
    """
    Processes EventRecord and its links from a row.
    
    Args:
        row: The data row
        context: The population context
        resource_individual: The resource individual
        resource_base_id: The base ID of the resource
        row_num: The row number
        request_ind: The production request individual
        material_ind: The material individual
        time_interval_ind: The time interval individual
        shift_ind: The shift individual
        state_ind: The operational state individual
        reason_ind: The operational reason individual
        property_mappings: Optional property mappings dictionary
        
    Returns:
        The EventRecord individual or None
    """
    cls_EventRecord = context.get_class("EventRecord")
    if not cls_EventRecord: 
        return None

    start_time_for_label = getattr(time_interval_ind, "startTime", None) if time_interval_ind else "unknown_time"
    # Use interval base name if available, otherwise construct fallback
    interval_base_name = time_interval_ind.name if time_interval_ind else f"Interval_Row{row_num}_{resource_base_id}"
    event_record_base = f"Event_{interval_base_name}"
    event_labels = [f"Event for {resource_base_id} at {start_time_for_label}"]

    event_ind = get_or_create_individual(cls_EventRecord, event_record_base, context.onto, add_labels=event_labels)
    if not event_ind:
        pop_logger.error(f"Row {row_num}: Failed to create EventRecord individual '{event_record_base}'.")
        return None

    # --- Populate EventRecord Data Properties ---
    # Check if we can use dynamic property mappings
    if property_mappings and "EventRecord" in property_mappings:
        event_mappings = property_mappings["EventRecord"]
        apply_property_mappings(event_ind, event_mappings, row, context, "EventRecord", pop_logger)
    else:
        # --- Fallback to hardcoded property assignments if no mappings available ---
        pop_logger.debug("Using hardcoded property assignments (no dynamic mappings available)")
        context.set_prop_if_col_exists(event_ind, "operationType", 'OPERA_TYPE', row, safe_cast, str, pop_logger)
        context.set_prop_if_col_exists(event_ind, "rampUpFlag", 'RAMPUP_FLAG', row, safe_cast, bool, pop_logger, default=False)
        context.set_prop_if_col_exists(event_ind, "reportedDurationMinutes", 'TOTAL_TIME', row, safe_cast, float, pop_logger)

        # Time Metrics (Functional)
        time_metric_cols = {
            "businessExternalTimeMinutes": "BUSINESS_EXTERNAL_TIME",
            "plantAvailableTimeMinutes": "PLANT_AVAILABLE_TIME",
            "effectiveRuntimeMinutes": "EFFECTIVE_RUNTIME",
            "plantDecisionTimeMinutes": "PLANT_DECISION_TIME",
            "productionAvailableTimeMinutes": "PRODUCTION_AVAILABLE_TIME"
        }
        for prop_name, col_name in time_metric_cols.items():
            val = safe_cast(row.get(col_name), float)
            if val is not None:  # Only set if value is valid
                context.set_prop_if_col_exists(event_ind, prop_name, col_name, row, safe_cast, float, pop_logger)

        # --- Additional Performance Metrics from Spec ---
        # Time Metrics (Functional)
        additional_time_metrics = {
            "downtimeMinutes": "DOWNTIME",
            "runTimeMinutes": "RUN_TIME",
            "notEnteredTimeMinutes": "NOT_ENTERED",
            "waitingTimeMinutes": "WAITING_TIME",
            "plantExperimentationTimeMinutes": "PLANT_EXPERIMENTATION",
            "allMaintenanceTimeMinutes": "ALL_MAINTENANCE",
            "autonomousMaintenanceTimeMinutes": "AUTONOMOUS_MAINTENANCE",
            "plannedMaintenanceTimeMinutes": "PLANNED_MAINTENANCE"
        }
        for prop_name, col_name in additional_time_metrics.items():
            val = safe_cast(row.get(col_name), float)
            if val is not None:  # Only set if value is valid
                context.set_prop_if_col_exists(event_ind, prop_name, col_name, row, safe_cast, float, pop_logger)
        
        # Production Quantity Metrics (Functional)
        quantity_metrics = {
            "goodProductionQuantity": "GOOD_PRODUCTION_QTY",
            "rejectProductionQuantity": "REJECT_PRODUCTION_QTY"
        }
        for prop_name, col_name in quantity_metrics.items():
            val = safe_cast(row.get(col_name), int)
            if val is not None:  # Only set if value is valid
                context.set_prop_if_col_exists(event_ind, prop_name, col_name, row, safe_cast, int, pop_logger)
                
        # Additional Event Categorization Metrics
        context.set_prop_if_col_exists(event_ind, "aeModelCategory", 'AE_MODEL_CATEGORY', row, safe_cast, str, pop_logger)

    # --- Link EventRecord to other Individuals (Object Properties) ---
    # Link to resource (Line or Equipment) - involvesResource (Non-functional per spec, but logic likely implies 1:1)
    context.set_prop(event_ind, "involvesResource", resource_individual)

    # Link to ProductionRequest (Non-functional)
    if request_ind: 
        context.set_prop(event_ind, "associatedWithProductionRequest", request_ind)

    # Link to Material (Non-functional)
    if material_ind: 
        context.set_prop(event_ind, "usesMaterial", material_ind)

    # Link to TimeInterval (Functional)
    if time_interval_ind: 
        context.set_prop(event_ind, "occursDuring", time_interval_ind)

    # Link to Shift (Functional)
    if shift_ind: 
        context.set_prop(event_ind, "duringShift", shift_ind)

    # Link to OperationalState (Functional)
    if state_ind: 
        context.set_prop(event_ind, "eventHasState", state_ind)

    # Link to OperationalReason (Functional)
    if reason_ind: 
        context.set_prop(event_ind, "eventHasReason", reason_ind)

    return event_ind
