"""
Event linking module for the ontology generator.

This module provides functions for linking equipment events to line events.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set, Optional

from owlready2 import Thing, Ontology, ThingClass, PropertyClass

from ontology_generator.utils.logging import link_logger

def link_equipment_events_to_line_events(onto: Ontology,
                                        created_events_context: List[Tuple[Thing, Thing, Thing, Thing]],
                                        defined_classes: Dict[str, ThingClass],
                                        defined_properties: Dict[str, PropertyClass]) -> int:
    """
    Second pass function to link equipment EventRecords to their containing line EventRecords,
    using relaxed temporal containment logic.
    
    Handles cases where TimeInterval.startTime may be missing or invalid by skipping those events
    for linking rather than failing the entire process.
    
    Args:
        onto: The ontology
        created_events_context: List of tuples (event_ind, resource_ind, time_interval_ind, line_ind_associated)
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties
        
    Returns:
        The number of links created
    """
    link_logger.info("Starting second pass: Linking equipment events to line events (Enhanced Relaxed Temporal Logic)...")

    # --- Get required classes and properties ---
    cls_EventRecord = defined_classes.get("EventRecord")
    cls_ProductionLine = defined_classes.get("ProductionLine")
    cls_Equipment = defined_classes.get("Equipment")
    prop_isPartOfLineEvent = defined_properties.get("isPartOfLineEvent")
    # Optional: Inverse property
    prop_hasDetailedEquipmentEvent = defined_properties.get("hasDetailedEquipmentEvent")
    prop_startTime = defined_properties.get("startTime")
    prop_endTime = defined_properties.get("endTime")

    if not all([cls_EventRecord, cls_ProductionLine, cls_Equipment, prop_isPartOfLineEvent, prop_startTime, prop_endTime]):
        link_logger.error("Missing essential classes or properties (EventRecord, ProductionLine, Equipment, isPartOfLineEvent, startTime, endTime) for linking. Aborting.")
        return 0  # Return count of links created

    # --- Configure Linking Parameters ---
    # Time buffer for edge cases: allows equipment events that start slightly before/after line events
    # This helps account for minor clock sync issues or timing discrepancies
    TIME_BUFFER_MINUTES = 5
    time_buffer = timedelta(minutes=TIME_BUFFER_MINUTES)
    
    # Default duration to assume for events with missing end times
    DEFAULT_EVENT_DURATION_HOURS = 2
    default_duration = timedelta(hours=DEFAULT_EVENT_DURATION_HOURS)
    
    link_logger.info(f"Using temporal linking parameters: Buffer={TIME_BUFFER_MINUTES} minutes, Default Duration={DEFAULT_EVENT_DURATION_HOURS} hours")

    # --- Prepare Lookups ---
    line_events_by_line: Dict[Thing, List[Tuple[Thing, Optional[datetime], Optional[datetime]]]] = defaultdict(list)
    equipment_events_to_link: List[Tuple[Thing, Thing, Optional[datetime], Optional[datetime]]] = []  # (eq_event, line_ind, start, end)

    # Create tracking for statistics and diagnostics
    missing_start_count = 0
    missing_end_count = 0
    inferred_end_count = 0
    
    link_logger.debug("Indexing created events...")
    processed_intervals = 0
    skipped_intervals = 0
    for event_ind, resource_ind, time_interval_ind, associated_line_ind in created_events_context:
        start_time = None
        end_time = None
        
        # Skip if no interval exists
        if not time_interval_ind:
            link_logger.warning(f"Event {event_ind.name} has no associated TimeInterval. Cannot use for linking.")
            skipped_intervals += 1
            continue
        
        # Try to get start and end times safely
        try:
            start_time = getattr(time_interval_ind, prop_startTime.python_name, None)
            end_time = getattr(time_interval_ind, prop_endTime.python_name, None)
            processed_intervals += 1
            
            # Count missing times for diagnostics
            if not isinstance(start_time, datetime):
                missing_start_count += 1
            if not isinstance(end_time, datetime):
                missing_end_count += 1
                
        except Exception as e:
            link_logger.warning(f"Error retrieving time properties from interval {time_interval_ind.name}: {e}")
            skipped_intervals += 1
            continue
        
        # Basic validation: Need at least a start time for meaningful comparison
        # Explicitly check if it's a datetime to avoid type errors later
        if not isinstance(start_time, datetime):
            interval_name = getattr(time_interval_ind, 'name', 'UnnamedInterval')
            link_logger.warning(f"Event {event_ind.name} has invalid or missing start time in interval {interval_name}. Cannot use for linking.")
            skipped_intervals += 1
            continue  # Skip this event for linking if start time is bad

        # Check if it's a line event or equipment event
        if isinstance(resource_ind, cls_ProductionLine):
            if associated_line_ind and associated_line_ind.name == resource_ind.name:
                line_events_by_line[associated_line_ind].append((event_ind, start_time, end_time))
                link_logger.debug(f"Indexed line event {event_ind.name} for line {associated_line_ind.name}")
            else:
                 link_logger.warning(f"Line event {event_ind.name} has mismatch between resource ({resource_ind.name}) and stored associated line ({associated_line_ind.name if associated_line_ind else 'None'}). Skipping indexing.")
        elif isinstance(resource_ind, cls_Equipment):
            if associated_line_ind:
                equipment_events_to_link.append((event_ind, associated_line_ind, start_time, end_time))

    link_logger.info(f"Indexed {len(line_events_by_line)} lines with line events.")
    link_logger.info(f"Found {len(equipment_events_to_link)} equipment events with context to potentially link.")
    link_logger.info(f"Processed {processed_intervals} valid intervals, skipped {skipped_intervals} invalid/incomplete intervals.")
    link_logger.info(f"Time data statistics: Missing start times: {missing_start_count}, Missing end times: {missing_end_count}")
    
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
    
    link_logger.info("Attempting to link equipment events to containing line events...")
    with onto:  # Use ontology context for modifications
        for eq_event_ind, line_ind, eq_start, eq_end in equipment_events_to_link:
            potential_parents = line_events_by_line.get(line_ind, [])
            parent_found = False

            # Equipment start time must be valid (already checked during indexing)
            if not isinstance(eq_start, datetime):
                continue

            # If equipment event has no end time, infer a reasonable end time for comparison purposes
            inferred_eq_end = None
            if not isinstance(eq_end, datetime):
                inferred_eq_end = eq_start + default_duration
                inferred_end_count += 1
            
            for line_event_ind, line_start, line_end in potential_parents:
                # Line event start time must be valid (defensive check)
                if not isinstance(line_start, datetime):
                    link_logger.debug(f"Skipping line event {line_event_ind.name} - invalid start time")
                    continue

                # --- Enhanced Temporal Containment Logic ---
                link = False
                link_method = "None"

                # Diagnostic information for logging interval comparison details
                eq_interval_str = f"{eq_start}" + (f" - {eq_end}" if isinstance(eq_end, datetime) else f" - (inferred: {inferred_eq_end})" if inferred_eq_end else " - NoEnd")
                line_interval_str = f"{line_start}" + (f" - {line_end}" if isinstance(line_end, datetime) else " - NoEnd")

                # 1. Check for Strict Containment (requires valid start/end for both)
                if isinstance(eq_end, datetime) and isinstance(line_end, datetime):
                    # Apply time buffer for start comparison (equipment can start slightly before line)
                    strict_cond1 = (line_start - time_buffer <= eq_start <= line_end)
                    # Apply time buffer for end comparison (equipment can end slightly after line)
                    strict_cond2 = (line_start <= eq_end <= line_end + time_buffer)
                    
                    if strict_cond1 and strict_cond2:
                        link = True
                        link_method = "Strict Containment"
                        link_logger.debug(f"Match via strict containment: Equipment event {eq_interval_str} within Line event {line_interval_str}")
                
                # 2. Check for Start Containment (if strict containment failed or missing end times)
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
                
                # 3. Check for End Containment if we have a real or inferred equipment end time
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
                
                # 4. Check for Temporal Overlap when both events have a start and at least one has an end time
                if not link and line_end is not None:
                    # Either the equipment event has a real end time or we use the inferred one
                    actual_eq_end = eq_end if isinstance(eq_end, datetime) else inferred_eq_end
                    
                    if actual_eq_end and ((eq_start <= line_end + time_buffer and actual_eq_end >= line_start - time_buffer)):
                        link = True
                        link_method = "Temporal Overlap" if isinstance(eq_end, datetime) else "Inferred Overlap"
                        link_logger.debug(f"Match via {link_method}: Equipment event {eq_interval_str} overlaps with Line event {line_interval_str}")

                # --- End of Enhanced Containment Logic ---

                if link:
                    try:
                        # Link: Equipment Event ---isPartOfLineEvent---> Line Event
                        current_parents = getattr(eq_event_ind, prop_isPartOfLineEvent.python_name, [])
                        if not isinstance(current_parents, list): 
                            current_parents = [current_parents] if current_parents is not None else []

                        if line_event_ind not in current_parents:
                            getattr(eq_event_ind, prop_isPartOfLineEvent.python_name).append(line_event_ind)
                            links_created += 1
                            linking_methods_used[link_method] += 1
                            link_logger.info(f"Linked ({link_method}): {eq_event_ind.name} isPartOfLineEvent {line_event_ind.name}")

                            # Optional: Link inverse if property exists
                            if prop_hasDetailedEquipmentEvent:
                                current_children = getattr(line_event_ind, prop_hasDetailedEquipmentEvent.python_name, [])
                                if not isinstance(current_children, list): 
                                    current_children = [current_children] if current_children is not None else []

                                if eq_event_ind not in current_children:
                                    getattr(line_event_ind, prop_hasDetailedEquipmentEvent.python_name).append(eq_event_ind)
                                    link_logger.debug(f"Linked Inverse: {line_event_ind.name} hasDetailedEquipmentEvent {eq_event_ind.name}")

                            parent_found = True
                            linked_events += 1
                            break  # Stop searching for parents for this equipment event
                        else:
                            # Log if the link already existed (useful for debugging duplicates/re-runs)
                            link_logger.debug(f"Link already exists: {eq_event_ind.name} isPartOfLineEvent {line_event_ind.name}. Skipping append.")
                            parent_found = True  # Treat existing link as success
                            linked_events += 1  # Count as linked since it's already linked
                            break


                    except Exception as e:
                        link_logger.error(f"Error creating link between {eq_event_ind.name} and {line_event_ind.name} (Method: {link_method}): {e}", exc_info=False)

            # Log if no parent was found after checking all candidates
            if not parent_found:
                failed_events += 1
                eq_interval_str = f"{eq_start}" + (f" - {eq_end}" if isinstance(eq_end, datetime) else f" - (inferred: {inferred_eq_end})" if inferred_eq_end else " - NoEnd")
                line_event_count = len(potential_parents)
                
                # Enhanced diagnostics for failed linking attempts
                if line_event_count > 0:
                    # Get the first few line events to show their times for diagnostics
                    sample_line_events = potential_parents[:3]
                    sample_intervals = []
                    for _, le_start, le_end in sample_line_events:
                        le_interval = f"{le_start}" + (f" - {le_end}" if isinstance(le_end, datetime) else " - NoEnd")
                        sample_intervals.append(le_interval)
                    
                    samples_str = ", ".join(sample_intervals)
                    link_logger.warning(f"Could not find suitable containing line event for equipment event {eq_event_ind.name} "
                                        f"(Interval: {eq_interval_str}) on line {line_ind.name}. "
                                        f"Checked {line_event_count} candidates. Sample line events: {samples_str}")
                else:
                    link_logger.warning(f"No line events found for line {line_ind.name} to link equipment event {eq_event_ind.name} (Interval: {eq_interval_str})")

    # Log detailed statistics about the linking process
    link_logger.info(f"Finished linking pass. Created {links_created} 'isPartOfLineEvent' relationships.")
    link_logger.info(f"Linking success rate: {linked_events}/{total_equipment_events} equipment events linked ({linked_events/total_equipment_events*100:.1f}% success)")
    link_logger.info(f"Inferred end times for {inferred_end_count} events with missing JOB_END_TIME_LOC values")
    
    # Log breakdown of linking methods used
    link_logger.info("Linking methods breakdown:")
    for method, count in linking_methods_used.items():
        link_logger.info(f"  - {method}: {count} links ({count/links_created*100:.1f}% of successful links)")
    
    return links_created
