"""
Event linking module for the ontology generator.

This module provides functions for linking equipment events to line events.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set, Optional

from owlready2 import Thing, Ontology, ThingClass, PropertyClass

from ontology_generator.utils.logging import link_logger
from ontology_generator.config import DEFAULT_EVENT_LINKING_BUFFER_MINUTES, DEFAULT_EVENT_DURATION_HOURS
from ontology_generator.population.core import PopulationContext

def link_equipment_events_to_line_events(onto: Ontology,
                                        created_events_context: List[Tuple[Thing, Thing, str, Thing]],
                                        defined_classes: Dict[str, ThingClass],
                                        defined_properties: Dict[str, PropertyClass],
                                        event_buffer_minutes: Optional[int] = None) -> Tuple[int, Optional[PopulationContext]]:
    """
    Second pass function to link equipment EventRecords to their containing line EventRecords,
    using relaxed temporal containment logic.
    
    Handles cases where TimeInterval.startTime may be missing or invalid by skipping those events
    for linking rather than failing the entire process.
    
    Args:
        onto: The ontology
        created_events_context: List of tuples (event_ind, resource_ind, resource_type, line_ind_associated)
                                where resource_type is "Equipment" or "Line"
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties
        event_buffer_minutes: Optional time buffer in minutes for temporal linking,
                             overrides the default value if provided
        
    Returns:
        A tuple containing:
        - The number of links created
        - The PopulationContext with updated property usage tracking
    """
    link_logger.info("Starting second pass: Linking equipment events to line events (Enhanced Relaxed Temporal Logic)...")

    # --- Get required classes and properties ---
    # TKT-004: Create a PopulationContext for property usage tracking
    property_is_functional = {}  # We'll fill this as needed
    context = PopulationContext(onto, defined_classes, defined_properties, property_is_functional)
    
    cls_EventRecord = defined_classes.get("EventRecord")
    cls_ProductionLine = defined_classes.get("ProductionLine")
    cls_Equipment = defined_classes.get("Equipment")
    prop_isPartOfLineEvent = defined_properties.get("isPartOfLineEvent")
    # Optional: Inverse property
    prop_hasDetailedEquipmentEvent = defined_properties.get("hasDetailedEquipmentEvent")
    prop_startTime = defined_properties.get("startTime")
    prop_endTime = defined_properties.get("endTime")
    prop_occursDuring = defined_properties.get("occursDuring")
    prop_involvesResource = defined_properties.get("involvesResource")
    prop_isPartOfProductionLine = defined_properties.get("isPartOfProductionLine")
    prop_eventId = defined_properties.get("eventId")  # Added for better event identification

    if not all([cls_EventRecord, cls_ProductionLine, cls_Equipment, prop_isPartOfLineEvent, prop_startTime, prop_endTime]):
        link_logger.error("Missing essential classes or properties (EventRecord, ProductionLine, Equipment, isPartOfLineEvent, startTime, endTime) for linking. Aborting.")
        return 0, None  # Return count of links created and None for context

    # TKT-004: Track property functionality for correct usage in _set_property_value
    for prop_name, prop in defined_properties.items():
        if hasattr(prop, "functional") and prop.functional:
            property_is_functional[prop_name] = True
        else:
            property_is_functional[prop_name] = False

    # --- Configure Linking Parameters ---
    # Time buffer for edge cases: allows equipment events that start slightly before/after line events
    # This helps account for minor clock sync issues or timing discrepancies
    TIME_BUFFER_MINUTES = event_buffer_minutes if event_buffer_minutes is not None else DEFAULT_EVENT_LINKING_BUFFER_MINUTES
    time_buffer = timedelta(minutes=TIME_BUFFER_MINUTES)
    
    # Default duration to assume for events with missing end times
    DEFAULT_DURATION_HOURS = DEFAULT_EVENT_DURATION_HOURS
    default_duration = timedelta(hours=DEFAULT_DURATION_HOURS)
    
    link_logger.info(f"Using temporal linking parameters: Buffer={TIME_BUFFER_MINUTES} minutes, Default Duration={DEFAULT_DURATION_HOURS} hours")

    # --- Prepare Lookups ---
    line_events_by_line: Dict[Thing, List[Tuple[Thing, Optional[datetime], Optional[datetime]]]] = defaultdict(list)
    equipment_events_to_link: List[Tuple[Thing, Thing, Optional[datetime], Optional[datetime]]] = []  # (eq_event, line_ind, start, end)

    # TKT-003: Ensure we're only processing events with the correct resource type
    line_events_count = 0
    equipment_events_count = 0
    skipped_wrong_type_count = 0
    
    # Create tracking for statistics and diagnostics
    missing_start_count = 0
    missing_end_count = 0
    inferred_end_count = 0
    
    # Added tracking for equipment events with no line association
    equipment_without_line = []
    
    link_logger.debug("Indexing created events...")
    processed_intervals = 0
    skipped_intervals = 0
    
    # Added tracking for equipment identification
    equipment_event_ids = {}  # Map event ind to human-readable event ID
    line_event_ids = {}       # Map event ind to human-readable event ID
    
    for event_ind, resource_ind, resource_type, _associated_line_ind in created_events_context:
        # TKT-003: Verify that resource_type accurately reflects the actual resource
        if resource_type == "Line" and not isinstance(resource_ind, cls_ProductionLine):
            link_logger.warning(f"Event {event_ind.name} has resource_type 'Line' but the resource is not a ProductionLine. Skipping.")
            skipped_wrong_type_count += 1
            continue
        elif resource_type == "Equipment" and not isinstance(resource_ind, cls_Equipment):
            link_logger.warning(f"Event {event_ind.name} has resource_type 'Equipment' but the resource is not an Equipment. Skipping.")
            skipped_wrong_type_count += 1
            continue
            
        # Capture event ID for better logging (if eventId property exists)
        if prop_eventId:
            event_id = getattr(event_ind, prop_eventId.python_name, event_ind.name)
            if resource_type == "Equipment":
                equipment_event_ids[event_ind] = event_id
                equipment_events_count += 1
            else:
                line_event_ids[event_ind] = event_id
                line_events_count += 1
        
        # Get time interval using the occursDuring property
        time_interval_ind = None
        if prop_occursDuring:
            # TKT-004: Check if property is properly initialized
            if not hasattr(prop_occursDuring, 'python_name'):
                event_id = getattr(event_ind, 'name', 'unknown')
                link_logger.error(f"TKT-004: Property 'occursDuring' is not properly initialized - missing python_name attribute. Cannot access time interval for event {event_id}")
                skipped_intervals += 1
                continue
                
            time_interval_ind = getattr(event_ind, prop_occursDuring.python_name, None)
            # Handle potential lists (owlready2 might return a list for object properties)
            if isinstance(time_interval_ind, list) and time_interval_ind:
                time_interval_ind = time_interval_ind[0]
        
        # Skip if no interval exists
        if not time_interval_ind:
            event_id = getattr(event_ind, prop_eventId.python_name, event_ind.name) if prop_eventId else event_ind.name
            link_logger.warning(f"Event {event_id} has no associated TimeInterval. Cannot use for linking.")
            skipped_intervals += 1
            continue
        
        start_time = None
        end_time = None
        
        # Try to get start and end times safely
        try:
            # TKT-004: Check if start/end time properties are properly initialized
            if not hasattr(prop_startTime, 'python_name'):
                event_id = getattr(event_ind, 'name', 'unknown')
                link_logger.error(f"TKT-004: Property 'startTime' is not properly initialized - missing python_name attribute. Cannot access start time for event {event_id}")
                skipped_intervals += 1
                continue
                
            if not hasattr(prop_endTime, 'python_name'):
                event_id = getattr(event_ind, 'name', 'unknown')
                link_logger.error(f"TKT-004: Property 'endTime' is not properly initialized - missing python_name attribute. Cannot access end time for event {event_id}")
                skipped_intervals += 1
                continue
            
            start_time = getattr(time_interval_ind, prop_startTime.python_name, None)
            end_time = getattr(time_interval_ind, prop_endTime.python_name, None)
            processed_intervals += 1
            
            # Count missing times for diagnostics
            if not isinstance(start_time, datetime):
                missing_start_count += 1
            if not isinstance(end_time, datetime):
                missing_end_count += 1
                
        except Exception as e:
            event_id = getattr(event_ind, prop_eventId.python_name, event_ind.name) if prop_eventId else event_ind.name
            link_logger.warning(f"Error retrieving time properties from interval for event {event_id}: {e}")
            skipped_intervals += 1
            continue
        
        # Basic validation: Need at least a start time for meaningful comparison
        # Explicitly check if it's a datetime to avoid type errors later
        if not isinstance(start_time, datetime):
            interval_name = getattr(time_interval_ind, 'name', 'UnnamedInterval')
            event_id = getattr(event_ind, prop_eventId.python_name, event_ind.name) if prop_eventId else event_ind.name
            link_logger.warning(f"Event {event_id} has invalid or missing start time in interval {interval_name}. Cannot use for linking.")
            skipped_intervals += 1
            continue  # Skip this event for linking if start time is bad

        # TKT-003: Check if it's a line event or equipment event strictly by resource_type
        if resource_type == "Line":
            # It's a line event
            line_events_by_line[resource_ind].append((event_ind, start_time, end_time))
            link_logger.debug(f"Indexed line event {getattr(event_ind, prop_eventId.python_name, event_ind.name) if prop_eventId else event_ind.name} for line {resource_ind.name}")
        elif resource_type == "Equipment":
            # It's an equipment event, find its associated line
            associated_line_ind = None
            if prop_isPartOfProductionLine:
                # TKT-004: Check if property is properly initialized
                if not hasattr(prop_isPartOfProductionLine, 'python_name'):
                    event_id = getattr(event_ind, 'name', 'unknown')
                    equipment_id = getattr(resource_ind, 'name', 'unknown')
                    link_logger.error(f"TKT-004: Property 'isPartOfProductionLine' is not properly initialized - missing python_name attribute. Cannot find associated line for equipment {equipment_id} in event {event_id}")
                    continue
                    
                associated_line_ind = getattr(resource_ind, prop_isPartOfProductionLine.python_name, None)
                # Handle potential lists (owlready2 might return a list for object properties)
                if isinstance(associated_line_ind, list) and associated_line_ind:
                    associated_line_ind = associated_line_ind[0]
            
            if associated_line_ind:
                equipment_events_to_link.append((event_ind, associated_line_ind, start_time, end_time))
                link_logger.debug(f"Found equipment event {getattr(event_ind, prop_eventId.python_name, event_ind.name) if prop_eventId else event_ind.name} for equipment {resource_ind.name} with line {associated_line_ind.name}")
            else:
                event_id = getattr(event_ind, prop_eventId.python_name, event_ind.name) if prop_eventId else event_ind.name
                equipment_without_line.append((event_id, resource_ind.name))
                link_logger.warning(f"Equipment event {event_id} for equipment {resource_ind.name} has no associated line. Cannot link.")

    # TKT-003: Log the counts of events by type for verification
    link_logger.info(f"TKT-003: Event type counts - Line events: {line_events_count}, Equipment events: {equipment_events_count}")
    if skipped_wrong_type_count > 0:
        link_logger.warning(f"TKT-003: Skipped {skipped_wrong_type_count} events due to resource type mismatch")
    
    # Log lines with no events
    lines_with_no_events = set()
    all_lines = onto.search(type=cls_ProductionLine)
    for line in all_lines:
        if line not in line_events_by_line:
            lines_with_no_events.add(line.name)

    link_logger.info(f"Indexed {len(line_events_by_line)} lines with line events.")
    link_logger.info(f"Found {len(equipment_events_to_link)} equipment events with context to potentially link.")
    link_logger.info(f"Processed {processed_intervals} valid intervals, skipped {skipped_intervals} invalid/incomplete intervals.")
    link_logger.info(f"Time data statistics: Missing start times: {missing_start_count}, Missing end times: {missing_end_count}")
    
    # Log lines with no events
    if lines_with_no_events:
        line_count = len(lines_with_no_events)
        link_logger.warning(f"Found {line_count} lines with no associated events. First 5: {', '.join(list(lines_with_no_events)[:5])}")
    
    # Log equipment with no line association
    if equipment_without_line:
        eq_count = len(equipment_without_line)
        link_logger.warning(f"Found {eq_count} equipment events with no line association. First 5: {[f'{eid} ({equ})' for eid, equ in equipment_without_line[:5]]}")
    
    if processed_intervals == 0 and (len(line_events_by_line) > 0 or len(equipment_events_to_link) > 0):
        link_logger.warning("Processed events but found 0 valid time intervals. Linking will likely fail.")
    
    if missing_end_count > 0:
        link_logger.info(f"Found {missing_end_count} events with missing end times - will apply enhanced linking logic")

    # --- Perform Linking ---
    links_created = 0
    total_equipment_events = len(equipment_events_to_link)
    linked_events = 0
    failed_events = 0
    linking_methods_used = defaultdict(int)
    
    # Enhanced failure tracking - TKT-004
    failed_eq_events = []
    
    # Track failure reasons
    failure_categories = {
        "no_line_events": 0,           # Line has no events at all
        "no_temporal_match": 0,        # No temporal match found between equipment and line events
        "time_gap_too_large": 0,       # Time gap between equipment and nearest line event exceeds buffer
        "equipment_outside_range": 0,   # Equipment event completely outside any line event's range
        "other": 0                     # Other unclassified failures
    }
    
    # Track nearest miss data for analysis
    nearest_misses = []
    
    link_logger.info("Attempting to link equipment events to containing line events...")
    with onto:  # Use ontology context for modifications
        for eq_event_ind, line_ind, eq_start, eq_end in equipment_events_to_link:
            potential_parents = line_events_by_line.get(line_ind, [])
            parent_found = False
            
            eq_id = equipment_event_ids.get(eq_event_ind, eq_event_ind.name)

            # Equipment start time must be valid (already checked during indexing)
            if not isinstance(eq_start, datetime):
                continue

            # If equipment event has no end time, infer a reasonable end time for comparison purposes
            inferred_eq_end = None
            if not isinstance(eq_end, datetime):
                inferred_eq_end = eq_start + default_duration
                inferred_end_count += 1
            
            # Track failed event details - TKT-004
            event_details = {
                "event_id": eq_id,
                "line": line_ind.name,
                "start_time": eq_start,
                "end_time": eq_end,
                "inferred_end_time": inferred_eq_end,
                "potential_parents_count": len(potential_parents),
                "nearest_line_event": None,
                "nearest_line_event_gap": None,
                "failure_reason": None
            }
                
            # Check if there are no line events at all for this line
            if not potential_parents:
                failure_categories["no_line_events"] += 1
                event_details["failure_reason"] = "No line-level events (EQUIPMENT_TYPE=Line) found or indexed for this line. Possible data limitation."
                failed_eq_events.append(event_details)
                failed_events += 1
                link_logger.warning(f"Equipment event {eq_id} has no potential parent line events. No line-level events (EQUIPMENT_TYPE=Line) were found/indexed for line {line_ind.name}. Verify source data.")
                continue
                
            # Track nearest line event for diagnostic purposes
            nearest_line_event = None
            min_gap = timedelta(days=999)  # A very large initial gap
            
            for line_event_ind, line_start, line_end in potential_parents:
                # Line event start time must be valid (defensive check)
                if not isinstance(line_start, datetime):
                    line_id = line_event_ids.get(line_event_ind, line_event_ind.name)
                    link_logger.debug(f"Skipping line event {line_id} - invalid start time")
                    continue

                # --- Enhanced Temporal Containment Logic ---
                link = False
                link_method = "None"

                # Diagnostic information for logging interval comparison details
                eq_interval_str = f"{eq_start}" + (f" - {eq_end}" if isinstance(eq_end, datetime) else f" - (inferred: {inferred_eq_end})" if inferred_eq_end else " - NoEnd")
                line_interval_str = f"{line_start}" + (f" - {line_end}" if isinstance(line_end, datetime) else " - NoEnd")
                
                # Calculate temporal distance for nearest miss analysis - TKT-004
                eq_actual_end = eq_end if isinstance(eq_end, datetime) else inferred_eq_end
                
                # Calculate gap between events for nearest miss analysis
                line_end_or_max = line_end if isinstance(line_end, datetime) else datetime.max
                
                start_gap = abs(eq_start - line_start)
                
                # Calculate end gap if both ends are available
                end_gap = None
                if isinstance(eq_actual_end, datetime) and isinstance(line_end, datetime):
                    end_gap = abs(eq_actual_end - line_end)
                
                # Calculate minimum gap for this line event
                current_gap = min(
                    start_gap,
                    end_gap if end_gap is not None else timedelta(days=999)
                )
                
                # Track the nearest line event
                if current_gap < min_gap:
                    min_gap = current_gap
                    line_id = line_event_ids.get(line_event_ind, line_event_ind.name)
                    nearest_line_event = {
                        "line_event_id": line_id,
                        "gap": current_gap,
                        "start_time": line_start,
                        "end_time": line_end
                    }

                # TKT-003: Improved temporal containment logic, prioritizing overlap detection
                
                # 1. Check for Strict Containment (requires valid start/end for both)
                if isinstance(eq_end, datetime) and isinstance(line_end, datetime):
                    # Equipment event is fully contained within line event (with buffer)
                    strict_contained = (
                        line_start - time_buffer <= eq_start <= line_end + time_buffer and
                        line_start - time_buffer <= eq_end <= line_end + time_buffer
                    )
                    
                    if strict_contained:
                        link = True
                        link_method = "Strict Containment"
                        link_logger.debug(f"Match via strict containment: Equipment event {eq_interval_str} within Line event {line_interval_str}")
                
                # 2. Check for Significant Overlap (at least 50% of equipment event overlaps with line event)
                if not link and (isinstance(eq_end, datetime) or inferred_eq_end) and isinstance(line_end, datetime):
                    actual_eq_end = eq_end if isinstance(eq_end, datetime) else inferred_eq_end
                    
                    # Calculate overlap duration
                    overlap_start = max(eq_start, line_start)
                    overlap_end = min(actual_eq_end, line_end)
                    
                    if overlap_start <= overlap_end:  # There is some overlap
                        overlap_duration = (overlap_end - overlap_start).total_seconds()
                        eq_duration = (actual_eq_end - eq_start).total_seconds()
                        
                        # If equipment event overlaps with line event for at least 50% of its duration
                        if overlap_duration >= 0.5 * eq_duration:
                            link = True
                            link_method = "Significant Overlap"
                            link_logger.debug(f"Match via significant overlap: Equipment event {eq_interval_str} overlaps with Line event {line_interval_str}")
                
                # 3. Check for Start Containment (equipment starts within line event timespan)
                if not link:
                    # Equipment starts within line event timespan (with buffer)
                    # - Equipment starts after or at the same time as line (minus buffer)
                    # - Line has no end OR equipment starts before line ends (plus buffer)
                    start_cond1 = (line_start - time_buffer <= eq_start)
                    start_cond2 = (line_end is None or eq_start <= line_end + time_buffer)
                    
                    if start_cond1 and start_cond2:
                        link = True
                        link_method = "Start Containment"
                        link_logger.debug(f"Match via start containment: Equipment event {eq_interval_str} starts within Line event {line_interval_str}")
                
                # 4. Check for End Containment if we have a real or inferred equipment end time
                if not link and (isinstance(eq_end, datetime) or inferred_eq_end):
                    actual_eq_end = eq_end if isinstance(eq_end, datetime) else inferred_eq_end
                    
                    # Equipment ends within line event timespan (with buffer)
                    # - Line has no end OR equipment ends before line ends (plus buffer)
                    # - Equipment ends after or at the same time as line starts (minus buffer)
                    end_cond1 = (line_end is None or actual_eq_end <= line_end + time_buffer)
                    end_cond2 = (line_start - time_buffer <= actual_eq_end)
                    
                    if end_cond1 and end_cond2:
                        link = True
                        link_method = "End Containment" if isinstance(eq_end, datetime) else "Inferred End Containment"
                        link_logger.debug(f"Match via {link_method}: Equipment event {eq_interval_str} ends within Line event {line_interval_str}")
                
                # 5. Check for Temporal Proximity when events don't overlap but are very close in time
                if not link:
                    # Calculate proximity between events
                    proximity = None
                    
                    if isinstance(line_end, datetime) and eq_start > line_end:
                        # Equipment event starts after line event ends
                        proximity = eq_start - line_end
                    elif isinstance(eq_end, datetime) and line_start > eq_end:
                        # Line event starts after equipment event ends
                        proximity = line_start - eq_end
                    elif isinstance(inferred_eq_end, datetime) and line_start > inferred_eq_end:
                        # Line event starts after inferred equipment event end
                        proximity = line_start - inferred_eq_end
                    
                    # If events are within very close proximity (half the buffer)
                    if proximity is not None and proximity <= time_buffer / 2:
                        link = True
                        link_method = "Close Temporal Proximity"
                        link_logger.debug(f"Match via close proximity: Equipment event {eq_interval_str} is {proximity} from Line event {line_interval_str}")

                # --- End of Enhanced Containment Logic ---

                if link:
                    try:
                        # TKT-003: Verify both events have the correct resource types before linking
                        # TKT-004: Check if property is properly initialized
                        if not hasattr(prop_involvesResource, 'python_name'):
                            eq_id = getattr(eq_event_ind, 'name', 'unknown')
                            line_id = getattr(line_event_ind, 'name', 'unknown')
                            link_logger.error(f"TKT-004: Property 'involvesResource' is not properly initialized - missing python_name attribute. Cannot verify resource types for events {eq_id} and {line_id}")
                            continue
                            
                        eq_resource = getattr(eq_event_ind, prop_involvesResource.python_name, None)
                        line_resource = getattr(line_event_ind, prop_involvesResource.python_name, None)
                        
                        # Get the first item if it's a list
                        if isinstance(eq_resource, list) and eq_resource:
                            eq_resource = eq_resource[0]
                        if isinstance(line_resource, list) and line_resource:
                            line_resource = line_resource[0]
                        
                        is_valid_resource_types = True
                        
                        # Check that equipment event links to an Equipment resource
                        if not isinstance(eq_resource, cls_Equipment):
                            link_logger.warning(f"TKT-003: Equipment event {eq_id} does not link to an Equipment resource. Cannot link to line event.")
                            is_valid_resource_types = False
                        
                        # Check that line event links to a ProductionLine resource
                        if not isinstance(line_resource, cls_ProductionLine):
                            line_id = line_event_ids.get(line_event_ind, line_event_ind.name)
                            link_logger.warning(f"TKT-003: Line event {line_id} does not link to a ProductionLine resource. Cannot link from equipment event.")
                            is_valid_resource_types = False
                        
                        if not is_valid_resource_types:
                            continue
                        
                        # TKT-004: Check if property is properly initialized
                        if not hasattr(prop_isPartOfLineEvent, 'python_name'):
                            eq_id = getattr(eq_event_ind, 'name', 'unknown')
                            line_id = getattr(line_event_ind, 'name', 'unknown')
                            link_logger.error(f"TKT-004: Property 'isPartOfLineEvent' is not properly initialized - missing python_name attribute. Cannot create link between events {eq_id} and {line_id}")
                            continue
                        
                        # Link: Equipment Event ---isPartOfLineEvent---> Line Event
                        context.set_prop(eq_event_ind, "isPartOfLineEvent", line_event_ind)
                        links_created += 1
                        linking_methods_used[link_method] += 1
                        link_logger.info(f"Linked ({link_method}): {eq_id} isPartOfLineEvent {line_id}")

                        # Optional: Link inverse if property exists
                        if prop_hasDetailedEquipmentEvent:
                            # TKT-004: Check if property is properly initialized
                            if not hasattr(prop_hasDetailedEquipmentEvent, 'python_name'):
                                link_logger.warning(f"TKT-004: Property 'hasDetailedEquipmentEvent' is not properly initialized - missing python_name attribute. Skipping inverse link.")
                            else:
                                context.set_prop(line_event_ind, "hasDetailedEquipmentEvent", eq_event_ind)
                                link_logger.debug(f"Linked Inverse: {line_id} hasDetailedEquipmentEvent {eq_id}")

                        parent_found = True
                        linked_events += 1
                        break  # Stop searching for parents for this equipment event
                    except Exception as e:
                        line_id = line_event_ids.get(line_event_ind, line_event_ind.name)
                        link_logger.error(f"Error linking equipment event {eq_id} to line event {line_id}: {e}")
                        continue
                    
            if not parent_found:
                failed_events += 1
                
                # Record nearest line event details for diagnostics - TKT-004
                if nearest_line_event:
                    event_details["nearest_line_event"] = nearest_line_event["line_event_id"]
                    event_details["nearest_line_event_gap"] = str(nearest_line_event["gap"])
                    
                    # Classify failure reason
                    if nearest_line_event["gap"] > time_buffer:
                        event_details["failure_reason"] = f"Time gap too large: {nearest_line_event['gap']} > buffer {time_buffer}"
                        failure_categories["time_gap_too_large"] += 1
                        
                        # Add to nearest misses for pattern analysis if gap is within a reasonable threshold (e.g., 2x buffer)
                        if nearest_line_event["gap"] < time_buffer * 5:  # Track near misses within 5x buffer
                            nearest_misses.append({
                                "equipment_event": eq_id,
                                "line_event": nearest_line_event["line_event_id"],
                                "gap": nearest_line_event["gap"],
                                "eq_start": eq_start,
                                "eq_end": eq_end if isinstance(eq_end, datetime) else inferred_eq_end,
                                "line_start": nearest_line_event["start_time"],
                                "line_end": nearest_line_event["end_time"],
                            })
                    else:
                        event_details["failure_reason"] = "Failed despite being within time buffer - check containment logic"
                        failure_categories["other"] += 1
                else:
                    event_details["failure_reason"] = "All line events completely outside equipment event range"
                    failure_categories["equipment_outside_range"] += 1
                
                failed_eq_events.append(event_details)
                link_logger.warning(f"Could not find suitable parent line event for equipment event {eq_id}")
    
    # --- Detailed Failure Analysis - TKT-004 ---
    if failed_events > 0:
        link_logger.warning(f"FAILURE ANALYSIS: {failed_events} equipment events could not be linked")
        link_logger.warning("Failure categories:")
        for category, count in failure_categories.items():
            if count > 0:
                link_logger.warning(f"  • {category}: {count} events")
        
        # Log details of all failed events
        link_logger.warning("Detailed failure information for failed equipment events:")
        for i, event in enumerate(failed_eq_events):
            link_logger.warning(f"Unlinked Equipment Event #{i+1}: {event['event_id']}")
            link_logger.warning(f"  • Line: {event['line']}")
            link_logger.warning(f"  • Start Time: {event['start_time']}")
            link_logger.warning(f"  • End Time: {event['end_time'] if event['end_time'] else event['inferred_end_time']}")
            link_logger.warning(f"  • Potential Line Events: {event['potential_parents_count']}")
            link_logger.warning(f"  • Nearest Line Event: {event['nearest_line_event']}")
            link_logger.warning(f"  • Nearest Gap: {event['nearest_line_event_gap']}")
            link_logger.warning(f"  • Failure Reason: {event['failure_reason']}")
        
        # Analyze time gaps patterns for near-misses
        if nearest_misses:
            avg_gap = sum((m["gap"].total_seconds() for m in nearest_misses), 0) / len(nearest_misses)
            min_gap = min(nearest_misses, key=lambda x: x["gap"].total_seconds())
            max_gap = max(nearest_misses, key=lambda x: x["gap"].total_seconds())
            
            link_logger.warning("Near Miss Analysis:")
            link_logger.warning(f"  • Total near misses: {len(nearest_misses)}")
            link_logger.warning(f"  • Average gap: {timedelta(seconds=avg_gap)}")
            link_logger.warning(f"  • Minimum gap: {min_gap['gap']} (Event: {min_gap['equipment_event']})")
            link_logger.warning(f"  • Maximum gap: {max_gap['gap']} (Event: {max_gap['equipment_event']})")
            link_logger.warning("  • Potential Adjustment: Consider increasing time buffer from "
                               f"{TIME_BUFFER_MINUTES} to {int(TIME_BUFFER_MINUTES * 2)} minutes to capture more near misses")
            
            # Suggest buffer adjustment based on near miss analysis
            suggested_buffer = 0
            
            # If most misses would be captured by doubling the buffer
            captured_by_double = sum(1 for m in nearest_misses if m["gap"] <= time_buffer * 2)
            if captured_by_double > len(nearest_misses) / 2:
                suggested_buffer = TIME_BUFFER_MINUTES * 2
            
            # If most misses would be captured by tripling the buffer
            captured_by_triple = sum(1 for m in nearest_misses if m["gap"] <= time_buffer * 3)
            if captured_by_triple > len(nearest_misses) * 0.8:  # 80% capture rate
                suggested_buffer = TIME_BUFFER_MINUTES * 3
            
            if suggested_buffer > 0:
                link_logger.warning(f"  • Recommended Buffer Adjustment: Increase to {suggested_buffer} minutes "
                                  f"(would capture {captured_by_double}/{len(nearest_misses)} near misses at 2x, "
                                  f"{captured_by_triple}/{len(nearest_misses)} at 3x)")
    
    # --- Report Results ---
    link_logger.info(f"Equipment Event Linking Complete: Created {links_created} links between equipment and line events")
    link_logger.info(f"Linking stats: {linked_events}/{total_equipment_events} equipment events linked ({failed_events} failed)")
    
    # Report which linking methods were used - helps understand temporal matching patterns
    for method, count in linking_methods_used.items():
        link_logger.info(f"  - {method}: {count} links")
    
    # Report inferred end times usage
    if inferred_end_count > 0:
        link_logger.info(f"Used {inferred_end_count} inferred end times for linking")

    # TKT-003: Additional summary reporting for verification
    link_logger.info(f"\nTKT-003: Event Linking Verification")
    link_logger.info(f"  • Total line events processed: {line_events_count}")
    link_logger.info(f"  • Total equipment events processed: {equipment_events_count}")
    link_logger.info(f"  • Equipment events successfully linked: {linked_events} ({linked_events/max(1, equipment_events_count)*100:.1f}%)")
    link_logger.info(f"  • Equipment events without line association: {len(equipment_without_line)}")
    
    # Print a summary breakdown of the linking results to stdout for visibility
    print(f"\n=== EVENT LINKING RESULTS ===")
    print(f"Total equipment events: {total_equipment_events}")
    print(f"Events successfully linked: {linked_events} ({linked_events/total_equipment_events*100:.1f}%)")
    print(f"Failed to link: {failed_events} ({failed_events/total_equipment_events*100:.1f}%)")
    
    if failed_events > 0:
        print("\nFailure breakdown:")
        for category, count in sorted(failure_categories.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                print(f"  • {category}: {count} ({count/failed_events*100:.1f}%)")
        
        if nearest_misses:
            print(f"\nNear misses (within 5x buffer): {len(nearest_misses)}")
            print(f"  Average gap: {timedelta(seconds=avg_gap)}")
            if suggested_buffer > 0:
                print(f"  Consider increasing buffer from {TIME_BUFFER_MINUTES} to {suggested_buffer} minutes")
    
    print(f"=== END EVENT LINKING RESULTS ===\n")
    
    return links_created, context
