"""
Event linking module for the ontology generator.

This module provides functions for linking equipment events to line events.
"""
from collections import defaultdict
from datetime import datetime
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
    
    Args:
        onto: The ontology
        created_events_context: List of tuples (event_ind, resource_ind, time_interval_ind, line_ind_associated)
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties
        
    Returns:
        The number of links created
    """
    link_logger.info("Starting second pass: Linking equipment events to line events (Relaxed Temporal Logic)...")

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

    # --- Prepare Lookups ---
    line_events_by_line: Dict[Thing, List[Tuple[Thing, Optional[datetime], Optional[datetime]]]] = defaultdict(list)
    equipment_events_to_link: List[Tuple[Thing, Thing, Optional[datetime], Optional[datetime]]] = []  # (eq_event, line_ind, start, end)

    link_logger.debug("Indexing created events...")
    processed_intervals = 0
    for event_ind, resource_ind, time_interval_ind, associated_line_ind in created_events_context:
        start_time = None
        end_time = None
        if time_interval_ind:
            start_time = getattr(time_interval_ind, prop_startTime.python_name, None)
            end_time = getattr(time_interval_ind, prop_endTime.python_name, None)
            processed_intervals += 1
            # Basic validation: Need at least a start time for meaningful comparison
            if not isinstance(start_time, datetime):
                link_logger.warning(f"Event {event_ind.name} has invalid or missing start time in interval {getattr(time_interval_ind, 'name', 'UnnamedInterval')}. Cannot use for linking.")
                continue  # Skip this event for linking if start time is bad
        else:
            link_logger.warning(f"Event {event_ind.name} has no associated TimeInterval. Cannot use for linking.")
            continue  # Skip this event if no interval

        # Check if it's a line event or equipment event
        if isinstance(resource_ind, cls_ProductionLine):
            if associated_line_ind == resource_ind:
                line_events_by_line[associated_line_ind].append((event_ind, start_time, end_time))
            else:
                 link_logger.warning(f"Line event {event_ind.name} has mismatch between resource ({resource_ind.name}) and stored associated line ({associated_line_ind.name if associated_line_ind else 'None'}). Skipping indexing.")
        elif isinstance(resource_ind, cls_Equipment):
            if associated_line_ind:
                equipment_events_to_link.append((event_ind, associated_line_ind, start_time, end_time))

    link_logger.info(f"Indexed {len(line_events_by_line)} lines with line events.")
    link_logger.info(f"Found {len(equipment_events_to_link)} equipment events with context to potentially link.")
    if processed_intervals == 0 and (len(line_events_by_line) > 0 or len(equipment_events_to_link) > 0):
        link_logger.warning("Processed events but found 0 valid time intervals. Linking will likely fail.")


    # --- Perform Linking ---
    links_created = 0
    link_logger.info("Attempting to link equipment events to containing line events...")
    with onto:  # Use ontology context for modifications
        for eq_event_ind, line_ind, eq_start, eq_end in equipment_events_to_link:
            potential_parents = line_events_by_line.get(line_ind, [])
            parent_found = False

            # Equipment start time must be valid (already checked during indexing)
            if not isinstance(eq_start, datetime):
                continue

            for line_event_ind, line_start, line_end in potential_parents:
                # Line event start time must be valid
                if not isinstance(line_start, datetime):
                    continue

                # --- Temporal Containment Logic (Modified for Relaxation) ---
                link = False
                link_method = "None"

                # 1. Check for Strict Containment (requires valid start/end for both)
                strict_cond1 = (line_start <= eq_start)
                strict_cond2 = False
                if isinstance(eq_end, datetime) and isinstance(line_end, datetime):
                    strict_cond2 = (eq_end <= line_end)

                if strict_cond1 and strict_cond2:
                    link = True
                    link_method = "Strict Containment"
                    link_logger.debug(f"Potential match via strict containment for {eq_event_ind.name} in {line_event_ind.name}")
                else:
                    # 2. Fallback: Check if eq_start is within the line interval
                    #    (Handles cases where line_end or eq_end might be None)
                    fallback_cond1 = (line_start <= eq_start)  # Eq starts at or after line starts
                    # Eq starts before line ends (or line never ends)
                    fallback_cond2 = (line_end is None or (isinstance(line_end, datetime) and eq_start < line_end))

                    if fallback_cond1 and fallback_cond2:
                        link = True
                        link_method = "Start-Time Containment"
                        link_logger.debug(f"Potential match via start-time containment for {eq_event_ind.name} in {line_event_ind.name}")

                # --- End of Containment Logic ---

                if link:
                    try:
                        # Link: Equipment Event ---isPartOfLineEvent---> Line Event
                        current_parents = getattr(eq_event_ind, prop_isPartOfLineEvent.python_name, [])
                        if not isinstance(current_parents, list): 
                            current_parents = [current_parents] if current_parents is not None else []

                        if line_event_ind not in current_parents:
                            getattr(eq_event_ind, prop_isPartOfLineEvent.python_name).append(line_event_ind)
                            links_created += 1
                            link_logger.info(f"Linked ({link_method}): {eq_event_ind.name} isPartOfLineEvent {line_event_ind.name}")  # Changed to INFO for successful links

                            # Optional: Link inverse if property exists
                            if prop_hasDetailedEquipmentEvent:
                                current_children = getattr(line_event_ind, prop_hasDetailedEquipmentEvent.python_name, [])
                                if not isinstance(current_children, list): 
                                    current_children = [current_children] if current_children is not None else []

                                if eq_event_ind not in current_children:
                                    getattr(line_event_ind, prop_hasDetailedEquipmentEvent.python_name).append(eq_event_ind)
                                    link_logger.debug(f"Linked Inverse: {line_event_ind.name} hasDetailedEquipmentEvent {eq_event_ind.name}")

                            parent_found = True
                            break  # Stop searching for parents for this equipment event
                        else:
                            # Log if the link already existed (useful for debugging duplicates/re-runs)
                            link_logger.debug(f"Link already exists: {eq_event_ind.name} isPartOfLineEvent {line_event_ind.name}. Skipping append.")
                            parent_found = True  # Treat existing link as success
                            break


                    except Exception as e:
                        link_logger.error(f"Error creating link between {eq_event_ind.name} and {line_event_ind.name} (Method: {link_method}): {e}", exc_info=False)

            # Log if no parent was found after checking all candidates
            if not parent_found:
                eq_interval_str = f"{eq_start}" + (f" - {eq_end}" if isinstance(eq_end, datetime) else " - NoEnd")
                line_event_count = len(potential_parents)
                link_logger.warning(f"Could not find suitable containing line event for equipment event {eq_event_ind.name} (Interval: {eq_interval_str}) on line {line_ind.name} (checked {line_event_count} candidates).")


    link_logger.info(f"Finished linking pass. Created {links_created} 'isPartOfLineEvent' relationships.")
    return links_created
