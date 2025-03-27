"""Functions to map data to ontology instances."""

from typing import Dict, Any, Optional
import logging
from datetime import datetime

from ontology.core import onto
from ontology.helpers import get_or_create_instance
from ontology.classes.assets import Plant, Line, Equipment
from ontology.classes.events import EventRecord
from ontology.classes.location import Country, StrategicLocation, PhysicalArea
from ontology.classes.organizational import (
    Division,
    SubDivision,
    FocusFactory,
    GlobalHierarchyArea,
    GlobalHierarchyCategory,
    PurchasingOrganization,
)
from ontology.classes.process import Material, ProductionOrder, Crew
from ontology.classes.time_related import TimeInterval, Shift
from ontology.classes.utilization import (
    UtilizationState,
    UtilizationReason,
    DowntimeState,
    RunningState,
    WaitingState,
    PlannedStopState,
    ChangeoverState,
    BusinessExternalState,
    UnknownState,
    MaintenanceReason,
    PlannedMaintenanceReason,
    AutonomousMaintenanceReason,
    UnplannedMaintenanceReason,
    ChangeoverReason,
    WaitingReason,
    OperationalReason,
    ExternalReason,
    QualityLossReason,
    SpeedLossReason,
    ProcessReason,
    ExperimentationReason,
    CleaningSanitationReason,
)

from utils.datetime_utils import parse_datetime_with_tz
from utils.string_utils import parse_equipment_base_type

logger = logging.getLogger(__name__)


def map_row_to_ontology(
    row_data: Dict[str, Any],
    equipment_sequence_map: Dict[str, Dict[str, Dict[str, Any]]],
    equipment_type_sequence_order: Dict[str, int],
) -> None:
    """Map a single data row to ontology instances.

    Args:
        row_data: Dictionary containing a single row of data
        equipment_sequence_map: Configuration for equipment sequences
        equipment_type_sequence_order: Default sequence order by equipment type
    """
    try:
        # Create plant instance
        plant = _create_plant_instance(row_data)

        # Create line instance
        line = _create_line_instance(row_data, plant)

        # Create equipment instance
        equipment = _create_equipment_instance(
            row_data, line, equipment_sequence_map, equipment_type_sequence_order
        )

        # Create event record
        event_record = _create_event_record(row_data, plant, line, equipment)

        # Add time interval
        _add_time_interval(row_data, event_record)

        # Add utilization state and reason
        _add_utilization_details(row_data, event_record)

        # Add material and order if applicable
        _add_process_context(row_data, event_record)

    except Exception as e:
        logger.error(f"Error mapping row to ontology: {e}")
        raise


def _create_plant_instance(row_data: Dict[str, Any]) -> Plant:
    """Create or retrieve a plant instance from row data."""
    plant_id = row_data.get("PLANT")
    if not plant_id:
        raise ValueError("Plant ID is required")

    # Create instance first without properties
    plant = get_or_create_instance(Plant, f"Plant_{plant_id}", {})

    # Then assign all properties as lists
    plant.plantId = [plant_id]

    # Handle optional properties
    plant_description = row_data.get("PLANT_DESCRIPTION")
    if plant_description:
        plant.plantDescription = [plant_description]

    # Add coordinates if available
    lat = row_data.get("PLANT_LATITUDE")
    long = row_data.get("PLANT_LONGITUDE")
    if lat is not None:
        plant.latitude = [float(lat)]
    if long is not None:
        plant.longitude = [float(long)]

    # Add country relationship if available
    country_name = row_data.get("PLANT_COUNTRY")
    if country_name:
        country = get_or_create_instance(
            Country, f"Country_{country_name}", {"countryName": country_name}
        )
        plant.locatedInCountry = [country]

    # Add strategic location if available
    strategic_location = row_data.get("PLANT_STRATEGIC_LOCATION")
    if strategic_location:
        sl = get_or_create_instance(
            StrategicLocation,
            f"StrategicLocation_{strategic_location}",
            {"locationName": strategic_location},
        )
        plant.hasStrategicLocation = [sl]

    # Create focus factory instance if available
    focus_factory_name = row_data.get("GH_FOCUSFACTORY")
    if focus_factory_name:
        focus_factory = get_or_create_instance(
            FocusFactory,
            f"FocusFactory_{focus_factory_name}",
            {"factoryName": focus_factory_name},
        )
        # Create bidirectional relationship
        if (
            not hasattr(plant, "hasFocusFactory")
            or focus_factory not in plant.hasFocusFactory
        ):
            plant.hasFocusFactory = (
                [focus_factory]
                if not hasattr(plant, "hasFocusFactory")
                else plant.hasFocusFactory + [focus_factory]
            )
        focus_factory.locatedInPlant = [plant]

    # Add division if available
    division_name = row_data.get("PLANT_DIVISION")
    if division_name:
        division = get_or_create_instance(
            Division, f"Division_{division_name}", {"divisionName": division_name}
        )
        plant.partOfDivision = [division]

    # Add sub-division if available
    subdivision_name = row_data.get("PLANT_SUB_DIVISION")
    if subdivision_name:
        subdivision = get_or_create_instance(
            SubDivision,
            f"SubDivision_{subdivision_name}",
            {"subdivisionName": subdivision_name},
        )
        plant.partOfSubDivision = [subdivision]

    return plant


def _create_line_instance(row_data: Dict[str, Any], plant: Plant) -> Line:
    """Create or retrieve a line instance from row data."""
    line_name = row_data.get("LINE_NAME")
    if not line_name:
        raise ValueError("Line name is required")

    # Create instance first without properties
    line = get_or_create_instance(Line, f"Line_{line_name}", {})

    # Then assign properties as lists
    line.lineName = [line_name]

    # Set relationships
    line.locatedInPlant = [plant]

    # Get or create focus factory instance
    focus_factory_name = row_data.get("GH_FOCUSFACTORY")
    focus_factory = None
    if focus_factory_name:
        focus_factory = get_or_create_instance(
            FocusFactory,
            f"FocusFactory_{focus_factory_name}",
            {"factoryName": focus_factory_name},
        )
        # Ensure focus factory is associated with plant
        if (
            not hasattr(plant, "hasFocusFactory")
            or focus_factory not in plant.hasFocusFactory
        ):
            plant.hasFocusFactory = (
                [focus_factory]
                if not hasattr(plant, "hasFocusFactory")
                else plant.hasFocusFactory + [focus_factory]
            )
        focus_factory.locatedInPlant = [plant]

        # Set line to be part of focus factory
        line.partOfFocusFactory = [focus_factory]

    # Add physical area if available
    physical_area = row_data.get("PHYSICAL_AREA")
    if physical_area:
        area = get_or_create_instance(
            PhysicalArea, f"PhysicalArea_{physical_area}", {"areaName": physical_area}
        )
        # Set area relationships
        line.locatedInArea = [area]

        # Connect area to focus factory if available
        if focus_factory:
            area.partOfFocusFactory = [focus_factory]
            if (
                not hasattr(focus_factory, "hasPhysicalArea")
                or area not in focus_factory.hasPhysicalArea
            ):
                focus_factory.hasPhysicalArea = (
                    [area]
                    if not hasattr(focus_factory, "hasPhysicalArea")
                    else focus_factory.hasPhysicalArea + [area]
                )

            # Also ensure area has hasLine relationship to line
            if not hasattr(area, "hasLine") or line not in area.hasLine:
                area.hasLine = (
                    [line] if not hasattr(area, "hasLine") else area.hasLine + [line]
                )

    return line


def _create_equipment_instance(
    row_data: Dict[str, Any],
    line: Line,
    equipment_sequence_map: Dict[str, Dict[str, Dict[str, Any]]],
    equipment_type_sequence_order: Dict[str, int],
) -> Equipment:
    """Create or retrieve an equipment instance from row data."""
    equipment_name = row_data.get("EQUIPMENT_NAME")
    if not equipment_name:
        raise ValueError("Equipment name is required")

    equipment_id = row_data.get("EQUIPMENT_ID")

    # Get line name safely
    line_name = None
    if hasattr(line, "lineName") and line.lineName:
        line_name = line.lineName[0]

    # Parse equipment base type from name or use direct mapping if available
    equipment_base_type = None

    # Check if this is actually a line-level record
    is_line_level = False
    if "EQUIPMENT_TYPE" in row_data and row_data.get("EQUIPMENT_TYPE") == "LINE":
        # Handle as line-level data
        equipment_base_type = "Line"
        is_line_level = True
    # Also check if equipment name equals line name (common line-level identifier)
    elif (
        equipment_name
        and row_data.get("LINE_NAME")
        and equipment_name == row_data.get("LINE_NAME")
    ):
        equipment_base_type = "Line"
        is_line_level = True
    else:
        # First try to get from direct mapping in the data if available
        if "EQUIPMENT_BASE_TYPE" in row_data and row_data["EQUIPMENT_BASE_TYPE"]:
            equipment_base_type = row_data["EQUIPMENT_BASE_TYPE"]
        # Otherwise try to extract from name
        elif line_name:
            equipment_base_type = parse_equipment_base_type(equipment_name, line_name)

        # If all else fails, extract the base type from the equipment name itself
        # Some equipment names might just be the base type without line prefix
        if not equipment_base_type and equipment_name:
            # Just use the equipment name as the base type
            equipment_base_type = equipment_name
            # Try to extract known equipment types
            for known_type in [
                "Filler",
                "Cartoner",
                "Bundler",
                "CasePacker",
                "Palletizer",
            ]:
                if known_type.lower() in equipment_name.lower():
                    equipment_base_type = known_type
                    break

    # Ensure we never set None value for equipment base type
    if equipment_base_type is None:
        equipment_base_type = "Unknown"

    # Create instance first without properties
    equipment = get_or_create_instance(Equipment, f"Equipment_{equipment_name}", {})

    # Then assign properties as lists
    equipment.equipmentName = [equipment_name]
    if equipment_id:
        equipment.equipmentId = [equipment_id]
    if equipment_base_type:
        equipment.equipmentBaseType = [equipment_base_type]

    # Add sequence order based on equipment type
    if (
        not is_line_level
        and equipment_base_type
        and equipment_base_type in equipment_type_sequence_order
    ):
        equipment.sequenceOrder = [equipment_type_sequence_order[equipment_base_type]]

    # Set basic relationships
    equipment.isPartOfLine = [line]

    # Inherit relationships from line
    if hasattr(line, "partOfFocusFactory") and line.partOfFocusFactory:
        equipment.partOfFocusFactory = line.partOfFocusFactory

    if hasattr(line, "locatedInArea") and line.locatedInArea:
        equipment.locatedInArea = line.locatedInArea

    # Apply equipment sequence relationships if available - only for actual equipment (not line-level records)
    if (
        not is_line_level
        and line_name
        and line_name in equipment_sequence_map
        and equipment_base_type
        and equipment_base_type in equipment_sequence_map[line_name]
    ):
        equipment_config = equipment_sequence_map[line_name][equipment_base_type]

        # Override sequence order if specified
        if "order" in equipment_config:
            equipment.sequenceOrder = [equipment_config["order"]]

        # Set upstream/downstream relationships
        if "upstream" in equipment_config:
            upstream_type = equipment_config["upstream"]
            for other_equip in onto.Equipment.instances():
                if (
                    hasattr(other_equip, "isPartOfLine")
                    and line in other_equip.isPartOfLine
                    and hasattr(other_equip, "equipmentBaseType")
                    and other_equip.equipmentBaseType
                    and other_equip.equipmentBaseType[0] == upstream_type
                ):
                    equipment.isImmediatelyDownstreamOf = [other_equip]
                    other_equip.isImmediatelyUpstreamOf = [equipment]
                    break

        if "downstream" in equipment_config:
            downstream_type = equipment_config["downstream"]
            for other_equip in onto.Equipment.instances():
                if (
                    hasattr(other_equip, "isPartOfLine")
                    and line in other_equip.isPartOfLine
                    and hasattr(other_equip, "equipmentBaseType")
                    and other_equip.equipmentBaseType
                    and other_equip.equipmentBaseType[0] == downstream_type
                ):
                    equipment.isImmediatelyUpstreamOf = [other_equip]
                    other_equip.isImmediatelyDownstreamOf = [equipment]
                    break

    return equipment


def _create_event_record(
    row_data: Dict[str, Any], plant: Plant, line: Line, equipment: Equipment
) -> EventRecord:
    """Create an event record instance from row data."""
    # Create a unique ID for the event record
    record_id = row_data.get(
        "record_id_str",
        f"{plant.name}_{line.name}_{equipment.name}_{row_data.get('START_TIME_UTC')}",
    )

    event_record = get_or_create_instance(EventRecord, f"EventRecord_{record_id}")

    # Set basic relationships
    event_record.occursAtPlant = [plant]
    event_record.occursOnLine = [line]
    event_record.involvesEquipment = [equipment]

    return event_record


def _add_time_interval(row_data: Dict[str, Any], event_record: EventRecord) -> None:
    """Add time interval to event record."""
    # Try to get start and end times from standard fields
    start_time_str = row_data.get("START_TIME_UTC")
    end_time_str = row_data.get("END_TIME_UTC")

    # If standard fields are missing, check for event-specific time fields
    if not start_time_str or not end_time_str:
        # Check for event-specific time fields based on utilization state
        state_desc = row_data.get("UTIL_STATE_DESCRIPTION", "").upper()

        # Different event types might use different time field patterns
        if "DOWNTIME" in state_desc:
            start_time_str = row_data.get("DOWNTIME_START_UTC") or start_time_str
            end_time_str = row_data.get("DOWNTIME_END_UTC") or end_time_str
        elif "RUNNING" in state_desc:
            start_time_str = row_data.get("RUNTIME_START_UTC") or start_time_str
            end_time_str = row_data.get("RUNTIME_END_UTC") or end_time_str
        elif "CHANGEOVER" in state_desc:
            start_time_str = row_data.get("CHANGEOVER_START_UTC") or start_time_str
            end_time_str = row_data.get("CHANGEOVER_END_UTC") or end_time_str

        # Add any other event-specific time patterns here

    # Create defaults if either time is still missing
    if not start_time_str or not end_time_str:
        from datetime import datetime, timedelta

        # Use a default if not available
        now = datetime.now()

        # Only log at TRACE level (effectively no logging in standard config)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Missing time information for event {event_record.name}, using default"
            )

        # Default start time is now
        start_time = now
        # Default end time is 1 minute after start
        end_time = now + timedelta(minutes=1)
    else:
        # Parse from strings
        start_time = parse_datetime_with_tz(start_time_str)
        end_time = parse_datetime_with_tz(end_time_str)

        # Check if parsing failed and use defaults if it did
        if not start_time or not end_time:
            from datetime import datetime, timedelta

            now = datetime.now()

            # Only log at TRACE level (effectively no logging in standard config)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"Failed to parse time information for event {event_record.name}, using default"
                )

            start_time = now
            end_time = now + timedelta(minutes=1)

    # Create the time interval
    interval = get_or_create_instance(
        TimeInterval,
        f"TimeInterval_{event_record.name}",
        {},
    )

    # Set properties as lists
    interval.startTime = [start_time]
    interval.endTime = [end_time]

    # Link to event record
    event_record.occursDuring = [interval]

    # Add duration if available, otherwise calculate
    duration = row_data.get("TOTAL_TIME_SECONDS")
    if duration is not None:
        try:
            event_record.stateDuration = [float(duration)]
        except (ValueError, TypeError):
            # Calculate duration if conversion fails
            duration_seconds = (end_time - start_time).total_seconds()
            event_record.stateDuration = [duration_seconds]
    else:
        # Calculate duration from time interval
        duration_seconds = (end_time - start_time).total_seconds()
        event_record.stateDuration = [duration_seconds]


def _add_utilization_details(
    row_data: Dict[str, Any], event_record: EventRecord
) -> None:
    """Add utilization state and reason to event record."""
    state_desc = row_data.get("UTIL_STATE_DESCRIPTION")
    reason_desc = row_data.get("UTIL_REASON_DESCRIPTION")
    record_id = row_data.get("record_id_str", "unknown")

    # Map state description to appropriate state class
    state = None
    if state_desc:
        # Use a unique name for each state instance based on record ID
        state_instance_name = f"State_{state_desc}_{record_id}"

        if "DOWNTIME" in state_desc:
            state = get_or_create_instance(
                DowntimeState, state_instance_name, {"stateDescription": state_desc}
            )
        elif "RUNNING" in state_desc:
            state = get_or_create_instance(
                RunningState, state_instance_name, {"stateDescription": state_desc}
            )
        elif "WAITING" in state_desc:
            state = get_or_create_instance(
                WaitingState, state_instance_name, {"stateDescription": state_desc}
            )
        elif "PLANNED" in state_desc:
            state = get_or_create_instance(
                PlannedStopState, state_instance_name, {"stateDescription": state_desc}
            )
        elif "CHANGEOVER" in state_desc:
            state = get_or_create_instance(
                ChangeoverState, state_instance_name, {"stateDescription": state_desc}
            )
        elif "EXTERNAL" in state_desc or "BUSINESS" in state_desc:
            state = get_or_create_instance(
                BusinessExternalState,
                state_instance_name,
                {"stateDescription": state_desc},
            )
        elif "NOT_ENTERED" in state_desc or "UNKNOWN" in state_desc:
            state = get_or_create_instance(
                UnknownState, state_instance_name, {"stateDescription": state_desc}
            )
        else:
            # Default to generic state
            state = get_or_create_instance(
                UtilizationState,
                state_instance_name,
                {"stateDescription": state_desc},
            )

    if state:
        event_record.hasState = [state]

    # Map reason description to appropriate reason class
    reason = None
    if reason_desc:
        # Use a unique name for each reason instance based on record ID
        reason_instance_name = f"Reason_{reason_desc}_{record_id}"

        if "PLANNED MAINTENANCE" in reason_desc:
            reason = get_or_create_instance(
                PlannedMaintenanceReason,
                reason_instance_name,
                {"reasonDescription": reason_desc},
            )
        elif "AUTONOMOUS MAINTENANCE" in reason_desc:
            reason = get_or_create_instance(
                AutonomousMaintenanceReason,
                reason_instance_name,
                {"reasonDescription": reason_desc},
            )
        elif "MAINTENANCE" in reason_desc:
            reason = get_or_create_instance(
                UnplannedMaintenanceReason,
                reason_instance_name,
                {"reasonDescription": reason_desc},
            )
        elif "CHANGEOVER" in reason_desc:
            reason = get_or_create_instance(
                ChangeoverReason,
                reason_instance_name,
                {"reasonDescription": reason_desc},
            )
        elif "WAITING" in reason_desc:
            reason = get_or_create_instance(
                WaitingReason, reason_instance_name, {"reasonDescription": reason_desc}
            )
        elif (
            "MEETING" in reason_desc
            or "TRAINING" in reason_desc
            or "BREAK" in reason_desc
        ):
            reason = get_or_create_instance(
                OperationalReason,
                reason_instance_name,
                {"reasonDescription": reason_desc},
            )
        elif "DEMAND" in reason_desc:
            reason = get_or_create_instance(
                ExternalReason, reason_instance_name, {"reasonDescription": reason_desc}
            )
        elif "QUALITY" in reason_desc:
            reason = get_or_create_instance(
                QualityLossReason,
                reason_instance_name,
                {"reasonDescription": reason_desc},
            )
        elif "SPEED" in reason_desc:
            reason = get_or_create_instance(
                SpeedLossReason,
                reason_instance_name,
                {"reasonDescription": reason_desc},
            )
        elif "JAM" in reason_desc or "ADJUSTMENT" in reason_desc:
            reason = get_or_create_instance(
                ProcessReason, reason_instance_name, {"reasonDescription": reason_desc}
            )
        elif "EXPERIMENT" in reason_desc:
            reason = get_or_create_instance(
                ExperimentationReason,
                reason_instance_name,
                {"reasonDescription": reason_desc},
            )
        elif "CLEANING" in reason_desc or "SANITIZATION" in reason_desc:
            reason = get_or_create_instance(
                CleaningSanitationReason,
                reason_instance_name,
                {"reasonDescription": reason_desc},
            )
        else:
            # Default to generic reason
            reason = get_or_create_instance(
                UtilizationReason,
                reason_instance_name,
                {"reasonDescription": reason_desc},
            )

    if reason:
        event_record.hasReason = [reason]


def _add_process_context(row_data: Dict[str, Any], event_record: EventRecord) -> None:
    """Add material, order, shift, and crew to event record."""
    # Add material if available
    material_id = row_data.get("MATERIAL_ID")
    if material_id:
        material = get_or_create_instance(
            Material,
            f"Material_{material_id}",
            {
                "materialId": material_id,
                "materialDescription": row_data.get("MATERIAL_DESC"),
            },
        )
        event_record.processesMaterial = [material]

    # Add production order if available
    order_id = row_data.get("PRODUCTION_ORDER_ID")
    if order_id:
        order = get_or_create_instance(
            ProductionOrder,
            f"Order_{order_id}",
            {
                "orderId": order_id,
                "orderDescription": row_data.get("PRODUCTION_ORDER_DESC"),
            },
        )
        event_record.relatesToOrder = [order]

    # Add shift if available
    shift_name = row_data.get("SHIFT_NAME")
    if shift_name:
        shift = get_or_create_instance(
            Shift, f"Shift_{shift_name}", {"shiftName": shift_name}
        )
        event_record.duringShift = [shift]

        # Add crew if available
        crew_id = row_data.get("CREW_ID")
        if crew_id:
            crew = get_or_create_instance(Crew, f"Crew_{crew_id}", {"crewId": crew_id})
            event_record.operatedByCrew = [crew]
