"""Event-related query functions for the manufacturing ontology."""

import owlready2 as owl
from typing import List, Optional
import logging
from datetime import datetime
from ontology.core import onto
from ontology.classes.events import EventRecord
from ontology.classes.assets import Plant, Line, Equipment
from ontology.classes.utilization import UtilizationState, UtilizationReason

logger = logging.getLogger(__name__)


def find_events_by_plant(plant: Plant) -> List[EventRecord]:
    """Find all event records for a given plant.

    Args:
        plant: The plant to find events for

    Returns:
        List of event records for the plant
    """
    matching_events = [
        e
        for e in onto.EventRecord.instances()
        if hasattr(e, "occursAtPlant") and plant in e.occursAtPlant
    ]
    logger.debug(f"Found {len(matching_events)} events for plant {plant.name}")
    return matching_events


def find_events_by_line(line: Line) -> List[EventRecord]:
    """Find all event records for a given line.

    Args:
        line: The line to find events for

    Returns:
        List of event records for the line
    """
    matching_events = [
        e
        for e in onto.EventRecord.instances()
        if hasattr(e, "occursOnLine") and line in e.occursOnLine
    ]
    logger.debug(f"Found {len(matching_events)} events for line {line.name}")
    return matching_events


def find_events_by_equipment(equipment: Equipment) -> List[EventRecord]:
    """Find all event records for a given equipment.

    Args:
        equipment: The equipment to find events for

    Returns:
        List of event records for the equipment
    """
    matching_events = [
        e
        for e in onto.EventRecord.instances()
        if hasattr(e, "involvesEquipment") and equipment in e.involvesEquipment
    ]
    logger.debug(f"Found {len(matching_events)} events for equipment {equipment.name}")
    return matching_events


def find_events_by_state(state: UtilizationState) -> List[EventRecord]:
    """Find all event records with a given utilization state.

    Args:
        state: The utilization state to find events for

    Returns:
        List of event records with the state
    """
    matching_events = [
        e
        for e in onto.EventRecord.instances()
        if hasattr(e, "hasState") and state in e.hasState
    ]
    logger.debug(f"Found {len(matching_events)} events with state {state.name}")
    return matching_events


def find_events_by_reason(reason: UtilizationReason) -> List[EventRecord]:
    """Find all event records with a given utilization reason.

    Args:
        reason: The utilization reason to find events for

    Returns:
        List of event records with the reason
    """
    matching_events = [
        e
        for e in onto.EventRecord.instances()
        if hasattr(e, "hasReason") and reason in e.hasReason
    ]
    logger.debug(f"Found {len(matching_events)} events with reason {reason.name}")
    return matching_events


def find_events_in_time_range(start: datetime, end: datetime) -> List[EventRecord]:
    """Find all event records within a time range.

    Args:
        start: Start time of the range
        end: End time of the range

    Returns:
        List of event records within the time range
    """
    matching_events = []
    for event in onto.EventRecord.instances():
        if hasattr(event, "occursDuring") and event.occursDuring:
            interval = event.occursDuring[0]
            if (
                hasattr(interval, "startTime")
                and interval.startTime
                and hasattr(interval, "endTime")
                and interval.endTime
            ):
                event_start = interval.startTime[0]
                event_end = interval.endTime[0]
                if event_start >= start and event_end <= end:
                    matching_events.append(event)

    logger.debug(f"Found {len(matching_events)} events in time range {start} to {end}")
    return matching_events
