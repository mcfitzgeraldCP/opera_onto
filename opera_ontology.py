#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consolidated Python script for Manufacturing Ontology definition, population,
and querying using Owlready2.
"""

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd
import owlready2 as owl
from typing import Dict, Any, Optional, List, Type, Union
from datetime import datetime, timedelta
import re

# =============================================================================
# Logging Setup
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Set specific logging levels for modules if needed (adjust as necessary)
# logging.getLogger("data.mappers").setLevel(logging.DEBUG)
# logging.getLogger("utils.string_utils").setLevel(logging.DEBUG)
# logging.getLogger("ontology.helpers").setLevel(logging.DEBUG)

# =============================================================================
# Configuration
# =============================================================================


def get_ontology_settings() -> Dict[str, Any]:
    """Get general ontology settings."""
    return {
        "ontology_iri": "http://example.org/manufacturing_revised_ontology.owl",
        "default_output_file": "manufacturing_ontology_revised_populated.owl",
        "format": "rdfxml",
    }


def get_equipment_type_sequence_order() -> Dict[str, int]:
    """Define the typical/default sequence order for known equipment types."""
    # Based on EQUIPMENT ORDERING section
    return {
        "Filler": 1,
        "Cartoner": 2,
        "Bundler": 3,
        "CaseFormer": 4,
        "CasePacker": 5,
        "CaseSealer": 6,
        "Palletizer": 7,
        # Add other known types if necessary
    }


def get_equipment_sequence_overrides() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Define line-specific equipment sequence overrides."""
    # Example overrides based on previous config examples
    return {
        # Example: VIPCO012 might have a non-standard sequence
        # "VIPCO012": {
        #     "TubeMaker": {"order": 1, "downstream": "CasePacker"}, # Assuming TubeMaker is parsed type
        #     "CasePacker": {"order": 2, "upstream": "TubeMaker"},
        # },
        # Example: FIPCO006 skips Cartoner, direct Filler->CasePacker
        # "FIPCO006": {
        #     "Filler": {"order": 1, "downstream": "CasePacker"},
        #     "CasePacker": {"order": 2, "upstream": "Filler"}, # Use actual parsed types
        # },
        # Add actual overrides based on real line configurations
    }


# =============================================================================
# Ontology Definition (Core, Classes, Properties)
# =============================================================================

# --- Core Ontology Setup ---
settings = get_ontology_settings()
ONTOLOGY_IRI = settings["ontology_iri"]
onto = owl.get_ontology(ONTOLOGY_IRI)

# --- Class Definitions ---
with onto:
    # Basic Thing
    class Thing(owl.Thing):
        pass

    # --- Assets ---
    class ManufacturingAsset(Thing):
        """Base class for all manufacturing assets."""

        pass

    class Plant(ManufacturingAsset):
        """A manufacturing plant/facility."""

        pass

    class Line(ManufacturingAsset):
        """A production line within a plant."""

        pass

    class Equipment(ManufacturingAsset):
        """A specific piece of equipment within a line."""

        pass

    # --- Location ---
    class Location(Thing):
        """Base class for geographical or organizational locations."""

        pass

    class Country(Location):
        pass

    class StrategicLocation(Location):
        pass

    class PhysicalArea(Location):
        """A physical area within a Focus Factory, containing Lines."""

        pass

    # --- Organizational ---
    class OrganizationalUnit(Thing):
        """Base class for organizational units."""

        pass

    class Division(OrganizationalUnit):
        pass

    class SubDivision(OrganizationalUnit):
        pass

    class FocusFactory(OrganizationalUnit):
        """A specialized production unit within a Plant (e.g., TPST)."""

        pass

    class GlobalHierarchyArea(OrganizationalUnit):
        pass  # e.g., TUBE/PACK from GH_AREA

    class GlobalHierarchyCategory(OrganizationalUnit):
        pass  # e.g., OC from GH_CATEGORY

    class PurchasingOrganization(OrganizationalUnit):
        pass

    class Crew(OrganizationalUnit):
        pass

    # --- Process Context ---
    class ProcessContext(Thing):
        """Base class for elements related to the production process."""

        pass

    class Material(ProcessContext):
        pass

    class ProductionOrder(ProcessContext):
        pass

    # --- Time Related ---
    class TimeRelated(Thing):
        pass

    class TimeInterval(TimeRelated):
        """Represents a specific interval in time with a start and end."""

        pass

    class Shift(TimeRelated):
        pass

    # --- Events ---
    class EventRecord(Thing):
        """Represents a single record from the source data, capturing a state over a time interval."""

        pass

    # --- Utilization States ---
    class UtilizationState(Thing):
        """The operational state of an asset during an EventRecord."""

        pass

    class OperationalState(UtilizationState):
        pass  # General category for running/producing

    class RunningState(OperationalState):
        pass  # Actively running/producing

    class NonOperationalState(UtilizationState):
        pass  # General category for not running

    class StoppedState(NonOperationalState):
        pass  # Intentionally stopped

    class PlannedStopState(StoppedState):
        pass  # Stopped for planned reasons (maint, breaks, meetings)

    class ChangeoverState(PlannedStopState):
        pass  # Specifically stopped for changeover

    class MaintenanceState(PlannedStopState):
        pass  # Specifically stopped for maintenance

    class OtherPlannedStopState(PlannedStopState):
        pass  # Breaks, meetings, cleaning etc.

    class UnplannedStopState(NonOperationalState):
        pass  # Unexpectedly stopped

    class DowntimeState(UnplannedStopState):
        pass  # Generic unplanned stop (breakdowns, jams etc.)

    class WaitingState(UnplannedStopState):
        pass  # Stopped waiting for external factor (material, operator, upstream)

    class ExternalNonAvailabilityState(UtilizationState):
        pass  # Not scheduled/available due to external factors

    class BusinessExternalState(ExternalNonAvailabilityState):
        pass  # e.g., No Demand

    class PlantDecisionState(ExternalNonAvailabilityState):
        pass  # e.g., Planned Shutdown (No Orders) - overlaps?

    class UnknownState(UtilizationState):
        pass  # State couldn't be determined

    # --- Utilization Reasons ---
    class UtilizationReason(Thing):
        """The reason behind a specific UtilizationState."""

        pass

    # Reasons for Planned Stops
    class PlannedReason(UtilizationReason):
        pass

    class MaintenanceReason(PlannedReason):
        pass

    class PlannedMaintenanceReason(MaintenanceReason):
        pass

    class AutonomousMaintenanceReason(MaintenanceReason):
        pass

    class CleaningSanitationReason(PlannedReason):
        pass

    class ChangeoverReason(PlannedReason):
        pass  # Reason is the changeover itself

    class OperationalPlannedReason(PlannedReason):
        pass  # Breaks, meetings, training

    class LunchBreakReason(OperationalPlannedReason):
        pass

    class MeetingTrainingReason(OperationalPlannedReason):
        pass

    class ExperimentationReason(PlannedReason):
        pass  # Planned trials

    # Reasons for Unplanned Stops (Downtime/Waiting)
    class UnplannedReason(UtilizationReason):
        pass

    class BreakdownReason(UnplannedReason):
        pass  # Equipment failure

    class JamReason(UnplannedReason):
        pass  # Material/product jam

    class AdjustmentReason(UnplannedReason):
        pass  # Minor adjustments needed

    class ProcessReason(UnplannedReason):
        pass  # Generic process issue causing stop (could overlap Jam/Adjust)

    class WaitingReason(UnplannedReason):
        pass  # Waiting for something/someone

    class WaitingForMaterialReason(WaitingReason):
        pass

    class WaitingForOperatorReason(WaitingReason):
        pass

    class WaitingForUpstreamReason(WaitingReason):
        pass

    class WaitingForDownstreamReason(WaitingReason):
        pass

    class WaitingOtherReason(WaitingReason):
        pass  # Generic wait

    # Reasons for External Non-Availability
    class ExternalReason(UtilizationReason):
        pass

    class NoDemandReason(ExternalReason):
        pass

    class ExternalFactorReason(ExternalReason):
        pass  # Weather, utility outage etc. (if applicable)

    # Other potential reasons (might overlap, use carefully)
    class QualityLossReason(UtilizationReason):
        pass  # If stop is *due* to quality issue detection

    class SpeedLossReason(UtilizationReason):
        pass  # If stop is *due* to speed issue detection (less common for stops)

    class UnknownReason(UtilizationReason):
        pass  # Reason couldn't be determined


# --- Property Definitions ---
with onto:
    # --- Object Properties (Relationships) ---

    # EventRecord Relationships
    class occursAtPlant(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [Plant]

    class occursOnLine(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [Line]

    class involvesEquipment(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [Equipment]  # Event usually relates to one specific equip/line instance

    class hasState(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [UtilizationState]  # An event captures one state

    class hasReason(owl.ObjectProperty):
        domain = [EventRecord]
        range = [
            UtilizationReason
        ]  # Could potentially have multiple reasons? Usually one primary. Let's keep non-functional for now.

    class occursDuring(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [TimeInterval]

    class processesMaterial(owl.ObjectProperty):
        domain = [EventRecord]
        range = [
            Material
        ]  # Maybe functional if only one material per event? Keep non-functional for flexibility.

    class relatesToOrder(owl.ObjectProperty):
        domain = [EventRecord]
        range = [ProductionOrder]  # Maybe functional? Keep non-functional.

    class duringShift(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [Shift]

    class operatedByCrew(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [Crew]

    # Asset Hierarchy & Location Relationships
    class locatedInPlant(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Line, Equipment, PhysicalArea, FocusFactory]
        range = [Plant]

    class hasFocusFactory(owl.ObjectProperty):
        domain = [Plant]
        range = [FocusFactory]
        inverse_property = locatedInPlant  # Plant can have multiple FFs

    class partOfFocusFactory(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [PhysicalArea, Line, Equipment]
        range = [FocusFactory]
        inverse_property = locatedInPlant  # Areas/Lines/Equip belong to one FF

    class hasArea(owl.ObjectProperty):
        domain = [FocusFactory]
        range = [PhysicalArea]
        inverse_property = partOfFocusFactory  # FF has multiple Areas

    class locatedInArea(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Line, Equipment]
        range = [PhysicalArea]  # Line/Equip in one Area

    class hasLine(owl.ObjectProperty):
        domain = [PhysicalArea]
        range = [Line]
        inverse_property = locatedInArea  # Area has multiple Lines

    class isPartOfLine(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Equipment]
        range = [Line]
        inverse_property = hasLine  # Equip on one Line

    class hasEquipment(owl.ObjectProperty):
        domain = [Line]
        range = [Equipment]
        inverse_property = isPartOfLine  # Line has multiple Equip

    class locatedInCountry(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Plant]
        range = [Country]

    class hasStrategicLocation(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Plant]
        range = [StrategicLocation]

    # Equipment Sequence Relationships
    class isImmediatelyUpstreamOf(owl.ObjectProperty):
        domain = [Equipment]
        range = [
            Equipment
        ]  # Can have multiple downstream in parallel? Keep non-functional.

    class isImmediatelyDownstreamOf(owl.ObjectProperty):
        domain = [Equipment]
        range = [Equipment]
        inverse_property = isImmediatelyUpstreamOf  # Can have multiple upstream in parallel? Keep non-functional.

    # Organizational Relationships (Example)
    class partOfDivision(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Plant, FocusFactory]
        range = [Division]

    class partOfSubDivision(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Plant, FocusFactory]
        range = [SubDivision]

    # --- Data Properties (Attributes) ---

    # Generic Identifiers/Names (Functional)
    class identifier(owl.DataProperty, owl.FunctionalProperty):
        range = [str]

    class name(owl.DataProperty, owl.FunctionalProperty):
        range = [str]

    class description(owl.DataProperty):
        range = [str]  # Descriptions might not always be functional if multiple exist

    # TimeInterval Properties (Functional)
    class startTime(owl.DataProperty, owl.FunctionalProperty):
        domain = [TimeInterval]
        range = [datetime]

    class endTime(owl.DataProperty, owl.FunctionalProperty):
        domain = [TimeInterval]
        range = [datetime]

    # Plant Properties (Functional where applicable)
    class plantId(identifier):
        domain = [Plant]

    class plantName(name):
        domain = [Plant]  # Use PLANT_DESCRIPTION?

    class plantDescription(description):
        domain = [Plant]

    class latitude(owl.DataProperty, owl.FunctionalProperty):
        domain = [Plant]
        range = [float]

    class longitude(owl.DataProperty, owl.FunctionalProperty):
        domain = [Plant]
        range = [float]

    class countryCode(identifier):
        domain = [Country]  # From PLANT_COUNTRY

    class countryName(name):
        domain = [Country]  # From PLANT_COUNTRY_DESCRIPTION

    # Add other PLANT_ fields as needed (facilityType, postalCode, etc.)

    # Line Properties (Functional)
    class lineId(identifier):
        domain = [Line]  # Use LINE_NAME?

    class lineName(name):
        domain = [Line]

    # Equipment Properties (Functional where applicable)
    class equipmentId(identifier):
        domain = [Equipment]  # From EQUIPMENT_ID

    class equipmentName(name):
        domain = [Equipment]  # From EQUIPMENT_NAME

    class equipmentBaseType(owl.DataProperty, owl.FunctionalProperty):
        domain = [Equipment]
        range = [str]  # Parsed type: Filler, Cartoner etc.

    class equipmentModel(owl.DataProperty):
        domain = [Equipment]
        range = [
            str
        ]  # From EQUIPMENT_MODEL, might not be functional if multiple models?

    class sequenceOrder(owl.DataProperty, owl.FunctionalProperty):
        domain = [Equipment]
        range = [int]

    # Add other equipment fields: COMPLEXITY, MODEL (second one?)

    # FocusFactory, Area, Org Properties (Functional)
    class focusFactoryName(name):
        domain = [FocusFactory]

    class areaName(name):
        domain = [PhysicalArea]

    class divisionName(name):
        domain = [Division]

    class subdivisionName(name):
        domain = [SubDivision]

    # Material Properties (Functional where applicable)
    class materialId(identifier):
        domain = [Material]

    class materialDescription(description):
        domain = [Material]

    class materialUOM(owl.DataProperty, owl.FunctionalProperty):
        domain = [Material]
        range = [str]

    # Add SIZE_TYPE, UOM_ST, PRIMARY_CONV_FACTOR etc.

    # Production Order Properties (Functional)
    class orderId(identifier):
        domain = [ProductionOrder]

    class orderDescription(description):
        domain = [ProductionOrder]

    class orderRate(owl.DataProperty, owl.FunctionalProperty):
        domain = [ProductionOrder]
        range = [float]

    class orderRateUOM(owl.DataProperty, owl.FunctionalProperty):
        domain = [ProductionOrder]
        range = [str]

    # Shift/Crew Properties (Functional)
    class shiftName(name):
        domain = [Shift]

    class crewId(identifier):
        domain = [Crew]

    # EventRecord Properties (Functional where applicable)
    class calculatedDurationSeconds(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # Calculated from start/end timestamps

    class reportedDurationMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # From TOTAL_TIME column

    # AE Model Time Components (All in Minutes from source data - Functional Floats)
    class businessExternalTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class plantAvailableTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class effectiveRuntimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class plantDecisionTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class productionAvailableTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class downtimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # DOWNTIME column

    class runTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # RUN_TIME column

    class notEnteredTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # NOT_ENTERED column

    class waitingTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # WAITING_TIME column

    class plantExperimentationTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # PLANT_EXPERIMENTATION column

    class allMaintenanceTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # ALL_MAINTENANCE column

    class autonomousMaintenanceTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # AUTONOMOUS_MAINTENANCE column

    class plannedMaintenanceTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # PLANNED_MAINTENANCE column

    class changeoverDurationMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # CHANGEOVER_DURATION column

    class cleaningSanitizationTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # CLEANING_AND_SANITIZATION column

    class lunchBreakTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # LUNCH_AND_BREAK column (or LUNCH + BREAK)

    class meetingTrainingTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # MEETING_AND_TRAINING column

    class noDemandTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # NO_DEMAND column

    # Production Quantities (Functional Floats/Ints)
    class goodProductionQty(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # Use float for safety

    class rejectProductionQty(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    # Utilization State/Reason Descriptions (Functional)
    class stateDescription(description):
        domain = [UtilizationState]  # Keep original description on the state type

    class reasonDescription(description):
        domain = [UtilizationReason]  # Keep original description on the reason type

    # Other potential properties
    class rampUpFlag(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [bool]

    # Add properties for CO_TYPE, SOURCE_DATASET etc. if needed

# =============================================================================
# Utility Functions
# =============================================================================


def parse_datetime_with_tz(timestamp_str: Optional[str]) -> Optional[datetime]:
    """Parse timestamps with timezone information (YYYY-MM-DD HH:MM:SS.fff +/-HHMM)."""
    if (
        pd.isna(timestamp_str)
        or not isinstance(timestamp_str, str)
        or not timestamp_str.strip()
    ):
        return None

    timestamp_str = timestamp_str.strip()

    try:
        # Format expected by source data: 'YYYY-MM-DD HH:MM:SS.fff +/-HHMM'
        # Example: 2025-02-10 22:45:02.000 -0500
        # Python's %z expects +/-HHMM

        # Check if timezone part exists and looks valid
        if " " in timestamp_str and ("+" in timestamp_str or "-" in timestamp_str[-6:]):
            parts = timestamp_str.rsplit(" ", 1)
            dt_part_str = parts[0]
            tz_part_str = parts[1]

            # Ensure tz_part is in +/-HHMM format (no colon)
            if ":" in tz_part_str:
                # Attempt to remove colon if present, e.g., +01:00 -> +0100
                tz_part_str = tz_part_str.replace(":", "")

            # Validate tz format (+/-HHMM)
            if not (
                len(tz_part_str) == 5
                and tz_part_str[0] in ("+", "-")
                and tz_part_str[1:].isdigit()
            ):
                raise ValueError("Timezone offset not in +/-HHMM format")

            # Reassemble and parse
            timestamp_to_parse = f"{dt_part_str}{tz_part_str}"
            # Use the most precise format string possible
            if "." in dt_part_str:
                format_str = "%Y-%m-%d %H:%M:%S.%f%z"
            else:
                format_str = "%Y-%m-%d %H:%M:%S%z"  # Handle cases without milliseconds

            dt_obj = datetime.strptime(timestamp_to_parse, format_str)
            return dt_obj
        else:
            # If no recognizable timezone, try parsing without it (as naive)
            logger.warning(
                f"Timestamp '{timestamp_str}' lacks recognizable timezone offset. Attempting naive parse."
            )
            if "." in timestamp_str:
                format_str = "%Y-%m-%d %H:%M:%S.%f"
            else:
                format_str = "%Y-%m-%d %H:%M:%S"
            dt_obj = datetime.strptime(timestamp_str, format_str)
            logger.warning(f"Parsed '{timestamp_str}' as NAIVE datetime.")
            return dt_obj

    except ValueError as e:
        # Fallback 1: Try ISO format (less likely for the sample data)
        try:
            # Replace first space with T for ISO compatibility if applicable
            iso_str = (
                timestamp_str.replace(" ", "T", 1)
                if " " in timestamp_str
                else timestamp_str
            )
            dt_obj = datetime.fromisoformat(iso_str)
            if dt_obj.tzinfo is None:
                logger.warning(
                    f"Parsed timestamp '{timestamp_str}' as naive datetime using fromisoformat fallback."
                )
            else:
                logger.warning(
                    f"Parsed timestamp '{timestamp_str}' using fromisoformat fallback."
                )
            return dt_obj
        except Exception as e2:
            logger.error(
                f"Error parsing timestamp '{timestamp_str}': Primary error: {e}, Fallback ISO error: {e2}"
            )
            return None
    except Exception as e_gen:
        logger.error(f"Unexpected error parsing timestamp '{timestamp_str}': {e_gen}")
        return None


def parse_equipment_base_type(equipment_name: str, line_name: str) -> str:
    """
    Extract the base equipment type (e.g., 'CasePacker') from the full equipment name
    (e.g., 'FIPCO006_CasePacker') using the line name.
    Handles potential trailing numbers (e.g., 'CasePacker2' -> 'CasePacker').
    Returns 'Unknown' if parsing fails or inputs are invalid.
    """
    if (
        not isinstance(equipment_name, str)
        or not isinstance(line_name, str)
        or not equipment_name
        or not line_name
    ):
        logger.debug(
            f"Invalid input for parsing equipment type: eq_name='{equipment_name}', line_name='{line_name}'"
        )
        return "Unknown"

    equipment_name = equipment_name.strip()
    line_name = line_name.strip()

    # Expected pattern: {LINE_NAME}_{BaseType}[OptionalNumber]
    prefix = f"{line_name}_"
    if equipment_name.startswith(prefix):
        base_type_part = equipment_name[len(prefix) :]

        # Remove potential trailing numbers
        base_type = re.sub(r"\d+$", "", base_type_part)

        if base_type:
            logger.debug(
                f"Parsed equipment type '{base_type}' from '{equipment_name}' using line '{line_name}'"
            )
            return base_type
        else:
            logger.warning(
                f"Equipment name '{equipment_name}' matches prefix '{prefix}' but has no type part."
            )
            return "Unknown"  # Or maybe return base_type_part if numbers are allowed? Stick to removing numbers per req.

    # Fallback: Check if equipment_name *is* one of the known types (case-insensitive)
    known_types_lower = {t.lower(): t for t in get_equipment_type_sequence_order()}
    if equipment_name.lower() in known_types_lower:
        base_type = known_types_lower[equipment_name.lower()]
        logger.debug(
            f"Equipment name '{equipment_name}' directly matched known type '{base_type}'."
        )
        return base_type

    # Fallback 2: If name contains underscore but not line prefix (less likely based on description)
    if "_" in equipment_name:
        possible_type_part = equipment_name.split("_")[-1]
        base_type = re.sub(r"\d+$", "", possible_type_part)
        if base_type:
            # Check if this looks like a known type? Might be too ambiguous.
            logger.debug(
                f"Potential equipment type '{base_type}' from last part of '{equipment_name}' (fallback)."
            )
            # Let's only return if it matches a known type to avoid random strings
            if base_type.lower() in known_types_lower:
                return known_types_lower[base_type.lower()]

    logger.debug(
        f"Could not parse equipment type from '{equipment_name}' using line '{line_name}'. Returning 'Unknown'."
    )
    return "Unknown"


def clean_string_value(value: Any) -> Optional[str]:
    """Clean string values, handling None and NaN, return None if invalid."""
    if pd.isna(value) or value is None:
        return None
    cleaned = str(value).strip()
    # Return None if the string is empty after stripping
    return cleaned if cleaned else None


def clean_numeric_value(value: Any) -> Optional[float]:
    """Clean numeric values, handling None/NaN/empty strings, return float or None."""
    if pd.isna(value) or value is None or value == "":
        return None
    try:
        # Handle potential comma separators if locale uses them (basic approach)
        if isinstance(value, str):
            value = value.replace(",", "")
        return float(value)
    except (ValueError, TypeError):
        logger.warning(
            f"Could not convert value '{value}' (type: {type(value)}) to float."
        )
        return None


def clean_boolean_value(value: Any) -> Optional[bool]:
    """Clean boolean values, handling None/NaN/strings, return bool or None."""
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        val_lower = value.strip().lower()
        if val_lower in ["true", "t", "yes", "y", "1"]:
            return True
        if val_lower in ["false", "f", "no", "n", "0"]:
            return False
    logger.warning(f"Could not convert value '{value}' to boolean.")
    return None  # Or raise error? Returning None seems safer.


# =============================================================================
# Ontology Helper Functions
# =============================================================================

# Cache for shared state/reason instances
_shared_instances_cache = {}


def get_or_create_instance(
    cls: Type[owl.Thing],
    instance_id: str,
    properties: Optional[Dict[str, Any]] = None,
    namespace: owl.Namespace = onto,
    use_cache: bool = False,  # Flag for states/reasons
) -> owl.Thing:
    """
    Get existing instance by identifier or create a new one.
    Handles functional properties by overwriting, non-functional by appending unique.
    Uses a cache for specific classes (like states/reasons) if use_cache=True.

    Args:
        cls: The owlready2 class to create an instance of.
        instance_id: Unique identifier string for the instance (will be sanitized).
        properties: Dictionary of property names and values to set/update.
        namespace: The ontology namespace to use.
        use_cache: If True, use the _shared_instances_cache for this class.

    Returns:
        The existing or newly created instance.
    """
    if not instance_id or not isinstance(instance_id, str):
        raise ValueError(
            f"Invalid instance_id provided for class {cls.__name__}: {instance_id}"
        )

    # Sanitize the instance name for OWL (replace invalid characters)
    # Basic sanitization, might need refinement based on IRI rules
    sanitized_id = re.sub(r"[^\w\-]+", "_", instance_id)
    instance_iri = f"{namespace.base_iri}{sanitized_id}"

    instance = None
    cache_key = (cls, sanitized_id)

    # Check cache first if requested
    if use_cache and cache_key in _shared_instances_cache:
        instance = _shared_instances_cache[cache_key]
        logger.debug(f"Retrieved '{sanitized_id}' of class {cls.__name__} from cache.")
        # Still update properties even if from cache? Yes, ensure consistency.
    else:
        # Check if instance already exists in the ontology by IRI
        instance = namespace.world.search_one(iri=instance_iri)
        if instance is not None:
            # Verify it's the correct type (or a subclass)
            if not isinstance(instance, cls):
                logger.error(
                    f"IRI conflict: Found existing instance <{instance_iri}> but it is not of type {cls.__name__} (it's {type(instance).__name__}). Returning None."
                )
                # Or raise an error? Returning None might hide issues. Let's raise.
                raise TypeError(
                    f"IRI conflict: Found existing instance <{instance_iri}> but it is not of type {cls.__name__} (it's {type(instance).__name__})."
                )
            else:
                logger.debug(
                    f"Retrieved existing instance '{sanitized_id}' of class {cls.__name__} from ontology."
                )
        else:
            # Create new instance
            logger.debug(
                f"Creating new instance '{sanitized_id}' of class {cls.__name__}."
            )
            instance = cls(sanitized_id, namespace=namespace)
            if use_cache:
                _shared_instances_cache[cache_key] = instance
                logger.debug(
                    f"Added '{sanitized_id}' of class {cls.__name__} to cache."
                )

    # Set/Update properties if provided
    if properties:
        for prop_name, value in properties.items():
            # Skip None values entirely - don't set properties to None
            if value is None:
                continue

            try:
                prop = getattr(
                    instance.__class__, prop_name, None
                )  # Get property object from class
                if prop is None:
                    logger.warning(
                        f"Property '{prop_name}' not defined for class {instance.__class__.__name__}. Skipping."
                    )
                    continue

                is_functional = hasattr(prop, "functional") and prop.functional
                is_object_prop = isinstance(prop, owl.ObjectProperty)

                current_value = getattr(instance, prop_name, None)

                if is_functional:
                    # Functional Property: Overwrite existing value or set if None
                    # We need to handle both DataProperty and ObjectProperty
                    if is_object_prop:
                        # Ensure value is an instance, not a list
                        if isinstance(value, list):
                            if len(value) > 1:
                                logger.warning(
                                    f"Attempting to set functional object property '{prop_name}' on {instance.name} with multiple values: {value}. Using only the first."
                                )
                            value = value[0] if value else None

                        if value is None:  # Don't unset if new value is None
                            continue

                        if current_value != [value]:  # Check if different
                            setattr(
                                instance, prop_name, [value]
                            )  # Owlready2 object properties are lists even if functional
                            logger.debug(
                                f"Set functional object property '{prop_name}' on {instance.name} to {value.name if hasattr(value,'name') else value}"
                            )

                    else:  # Functional Data Property
                        # Ensure value is not a list
                        if isinstance(value, list):
                            if len(value) > 1:
                                logger.warning(
                                    f"Attempting to set functional data property '{prop_name}' on {instance.name} with multiple values: {value}. Using only the first."
                                )
                            value = value[0] if value else None

                        if value is None:  # Don't unset if new value is None
                            continue

                        # Special check for datetime - direct comparison might fail with TZ awareness
                        is_datetime_prop = datetime in prop.range
                        needs_update = False
                        if (
                            is_datetime_prop
                            and isinstance(current_value, datetime)
                            and isinstance(value, datetime)
                        ):
                            needs_update = (
                                current_value != value
                            )  # Simple comparison works if both have TZ or both naive
                        elif current_value != value:
                            needs_update = True

                        if needs_update:
                            setattr(instance, prop_name, value)
                            logger.debug(
                                f"Set functional data property '{prop_name}' on {instance.name} to {value}"
                            )

                else:
                    # Non-Functional Property: Append value if not already present
                    if current_value is None:
                        current_value = []

                    # Ensure the value to add is not None
                    if value is None:
                        continue

                    # If the incoming value is a list itself, iterate and add unique items
                    values_to_add = value if isinstance(value, list) else [value]

                    updated = False
                    for val_item in values_to_add:
                        if val_item not in current_value:
                            current_value.append(val_item)
                            updated = True

                    if updated:
                        setattr(instance, prop_name, current_value)
                        logger.debug(
                            f"Updated non-functional property '{prop_name}' on {instance.name}"
                        )

            except Exception as e:
                logger.error(
                    f"Error setting property '{prop_name}' on instance {instance.name}: {e}",
                    exc_info=True,
                )

    return instance


# =============================================================================
# Data Handling Functions (Load, Preprocess, Map)
# =============================================================================


def load_csv_data(csv_path: str) -> pd.DataFrame:
    """Load data from CSV file."""
    logger.info(f"Loading data from {csv_path}")
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        # Add a unique record ID for easier instance naming/debugging if needed
        df["record_id_str"] = df.index.astype(str)
        logger.info(f"Loaded {len(df)} rows")
        return df
    except FileNotFoundError:
        logger.error(f"Error: {csv_path} not found")
        raise
    except Exception as e:
        logger.error(f"Error loading CSV: {e}")
        raise ValueError(f"Failed to parse CSV: {e}")


def preprocess_manufacturing_data(df: pd.DataFrame) -> pd.DataFrame:
    """Preprocess manufacturing data for ontology population."""
    processed_df = df.copy()
    logger.info("Starting preprocessing...")

    # --- Column Renaming (Optional but good practice) ---
    # Example: Rename confusing columns if necessary
    # processed_df.rename(columns={'OLD_NAME': 'NEW_NAME'}, inplace=True)

    # --- Data Type Conversions ---
    # Convert potential ID columns safely to strings (after handling NaNs)
    id_cols = [
        "EQUIPMENT_ID",
        "PRODUCTION_ORDER_ID",
        "MATERIAL_ID",
        "SHORT_MATERIAL_ID",
        "PLANT",
        "LINE_NAME",
        "EQUIPMENT_NAME",
    ]
    for col in id_cols:
        if col in processed_df.columns:
            # Fill NA with a placeholder temporarily if needed, convert to string, then replace placeholder if desired
            processed_df[col] = processed_df[col].apply(clean_string_value)
            logger.debug(f"Processed ID column: {col}")

    # Convert boolean columns
    boolean_cols = ["RAMPUP_FLAG"]
    for col in boolean_cols:
        if col in processed_df.columns:
            processed_df[col] = processed_df[col].apply(clean_boolean_value)
            # Optionally fill NA bools with False or keep as None/NaN? Let's keep None.
            # processed_df[col] = processed_df[col].fillna(False)
            logger.debug(f"Processed boolean column: {col}")

    # Convert numeric columns (AE Time components + others)
    numeric_cols = [
        "TOTAL_TIME",  # Primary duration in minutes
        "BUSINESS_EXTERNAL_TIME",
        "PLANT_AVAILABLE_TIME",
        "EFFECTIVE_RUNTIME",
        "PLANT_DECISION_TIME",
        "PRODUCTION_AVAILABLE_TIME",
        "GOOD_PRODUCTION_QTY",
        "REJECT_PRODUCTION_QTY",
        "DOWNTIME",
        "RUN_TIME",
        "NOT_ENTERED",
        "WAITING_TIME",
        "PLANT_EXPERIMENTATION",
        "ALL_MAINTENANCE",
        "AUTONOMOUS_MAINTENANCE",
        "PLANNED_MAINTENANCE",
        "CHANGEOVER_DURATION",
        "CLEANING_AND_SANITIZATION",
        "LUNCH_AND_BREAK",
        "LUNCH",
        "BREAK",  # Keep LUNCH/BREAK if needed separately
        "MEETING_AND_TRAINING",
        "NO_DEMAND",
        "PRIMARY_CONV_FACTOR",
        "PRODUCTION_ORDER_RATE",
        "SHIFT_DURATION_MIN",
        "UOM_ST",
        "UOM_ST_SAP",
        "TP_UOM",
        "PLANT_LATITUDE",
        "PLANT_LONGITUDE",
        "CHANGEOVER_COUNT",
        # "DAYS_MTD", "DAYS_YTD", # Keep commented unless known to be reliable numeric
    ]
    for col in numeric_cols:
        if col in processed_df.columns:
            original_dtype = processed_df[col].dtype
            processed_df[col] = processed_df[col].apply(clean_numeric_value)
            logger.debug(
                f"Processed numeric column: {col} (Original dtype: {original_dtype})"
            )

    # Convert remaining columns assumed to be string descriptions/categories
    # List columns NOT handled above (IDs, bools, numerics, times)
    all_cols = set(processed_df.columns)
    handled_cols = (
        set(id_cols)
        | set(boolean_cols)
        | set(numeric_cols)
        | set(
            [
                "JOB_START_TIME_LOC",
                "JOB_END_TIME_LOC",
                "SHIFT_START_DATE_LOC",
                "SHIFT_END_DATE_LOC",
                "PRODUCTIONDATE_DAY_LOC",
                "PRODUCTIONDATE_MONTH_LOC",
                "PRODUCTIONDATE_QUARTER_LOC",
                "PRODUCTIONDATE_YEAR_LOC",
                "record_id_str",
                "TOTAL_TIME_SECONDS",
            ]
        )
    )  # Also exclude date/time strings handled later

    string_cols = list(all_cols - handled_cols)
    for col in string_cols:
        if col in processed_df.columns:
            processed_df[col] = processed_df[col].apply(clean_string_value)
            logger.debug(f"Processed potential string column: {col}")

    # --- Extract Equipment Base Type (CRITICAL based on clarification #5) ---
    logger.info("Extracting Equipment Base Type from EQUIPMENT_NAME...")
    if "EQUIPMENT_NAME" in processed_df.columns and "LINE_NAME" in processed_df.columns:
        # Apply the parsing function row-wise
        # This will overwrite any existing 'EQUIPMENT_BASE_TYPE' column content
        processed_df["EQUIPMENT_BASE_TYPE_PARSED"] = processed_df.apply(
            lambda row: parse_equipment_base_type(
                row["EQUIPMENT_NAME"], row["LINE_NAME"]
            ),
            axis=1,
        )
        logger.info("Finished extracting Equipment Base Type.")

        # Log statistics on parsed types
        parsed_counts = processed_df["EQUIPMENT_BASE_TYPE_PARSED"].value_counts()
        logger.info(f"Equipment Base Type parsing results:\n{parsed_counts}")

        # Decide if we completely replace or just fill NaNs in an original column
        # Based on clarification, parsing EQUIPMENT_NAME is the source of truth.
        processed_df["EQUIPMENT_BASE_TYPE"] = processed_df["EQUIPMENT_BASE_TYPE_PARSED"]
        processed_df.drop(columns=["EQUIPMENT_BASE_TYPE_PARSED"], inplace=True)
        logger.info("Set 'EQUIPMENT_BASE_TYPE' based on parsed values.")

    else:
        logger.warning(
            "Missing EQUIPMENT_NAME or LINE_NAME columns. Cannot extract equipment base type."
        )
        if "EQUIPMENT_BASE_TYPE" not in processed_df.columns:
            processed_df["EQUIPMENT_BASE_TYPE"] = "Unknown"  # Ensure column exists

    # --- Handle Line vs Equipment Rows ---
    # The 'EQUIPMENT_TYPE' column indicates if the row is 'Line' or 'Equipment' level.
    # We need this info in the mapping step. Ensure it's clean.
    if "EQUIPMENT_TYPE" in processed_df.columns:
        processed_df["EQUIPMENT_TYPE"] = (
            processed_df["EQUIPMENT_TYPE"].apply(clean_string_value).fillna("Unknown")
        )
        logger.info(
            f"Cleaned EQUIPMENT_TYPE column. Value counts:\n{processed_df['EQUIPMENT_TYPE'].value_counts()}"
        )
    else:
        logger.warning(
            "EQUIPMENT_TYPE column missing. Assuming all rows are equipment level unless EQUIPMENT_NAME == LINE_NAME."
        )
        # Add a placeholder column maybe?
        processed_df["EQUIPMENT_TYPE"] = "Unknown"

    # --- Final Checks ---
    logger.info("Preprocessing finished.")
    # Example check: logger.info(f"Null counts after preprocessing:\n{processed_df.isnull().sum()}")

    return processed_df


# --- State and Reason Mapping Logic ---

# Define mappings from raw descriptions to ontology classes
# This needs to be customized based on the actual values in UTIL_STATE_DESCRIPTION and UTIL_REASON_DESCRIPTION
# Use lowercase for case-insensitive matching

STATE_CLASS_MAP = {
    # Running States
    "running": RunningState,
    "producing": RunningState,
    # Planned Stops
    "planned downtime": PlannedStopState,  # Generic Planned
    "changeover": ChangeoverState,
    "planned maintenance": MaintenanceState,  # Or more specific PlannedMaintenanceState if defined
    "autonomous maintenance": MaintenanceState,  # Or more specific AutonomousMaintenanceState if defined
    "cleaning": OtherPlannedStopState,  # Maps to CleaningSanitationReason
    "sanitization": OtherPlannedStopState,  # Maps to CleaningSanitationReason
    "break": OtherPlannedStopState,  # Maps to LunchBreakReason
    "lunch": OtherPlannedStopState,  # Maps to LunchBreakReason
    "meeting": OtherPlannedStopState,  # Maps to MeetingTrainingReason
    "training": OtherPlannedStopState,  # Maps to MeetingTrainingReason
    "experiment": OtherPlannedStopState,  # Maps to ExperimentationReason
    # Unplanned Stops
    "downtime": DowntimeState,  # Generic Unplanned
    "unplanned downtime": DowntimeState,
    "breakdown": DowntimeState,  # Maps to BreakdownReason
    "jammed": DowntimeState,  # Maps to JamReason
    "adjusting": DowntimeState,  # Maps to AdjustmentReason
    "waiting": WaitingState,
    "starved": WaitingState,  # Maps to WaitingForMaterial/Upstream Reason
    "blocked": WaitingState,  # Maps to WaitingForDownstream Reason
    # External
    "business external": BusinessExternalState,
    "no demand": BusinessExternalState,  # Maps to NoDemandReason
    "plant decision": PlantDecisionState,  # If distinct from BusinessExternal
    # Unknown
    "not entered": UnknownState,
    "unknown": UnknownState,
}

REASON_CLASS_MAP = {
    # Planned Maintenance
    "planned maintenance": PlannedMaintenanceReason,
    "preventive maintenance": PlannedMaintenanceReason,
    "autonomous maintenance": AutonomousMaintenanceReason,
    "operator maintenance": AutonomousMaintenanceReason,
    # Cleaning / Sanitation
    "cleaning": CleaningSanitationReason,
    "sanitization": CleaningSanitationReason,
    "cip": CleaningSanitationReason,
    # Changeovers
    "changeover": ChangeoverReason,
    "size change": ChangeoverReason,
    "product change": ChangeoverReason,
    "formula change": ChangeoverReason,
    # Operational Planned
    "lunch": LunchBreakReason,
    "break": LunchBreakReason,
    "meeting": MeetingTrainingReason,
    "training": MeetingTrainingReason,
    # Experimentation
    "trial": ExperimentationReason,
    "plant experimentation": ExperimentationReason,
    # Unplanned Breakdowns/Process
    "breakdown": BreakdownReason,
    "equipment failure": BreakdownReason,
    "mechanical failure": BreakdownReason,
    "electrical failure": BreakdownReason,
    "jammed": JamReason,
    "material jam": JamReason,
    "product jam": JamReason,
    "minor adjustment": AdjustmentReason,
    "adjustment": AdjustmentReason,
    "process issue": ProcessReason,  # Generic
    # Waiting
    "waiting for material": WaitingForMaterialReason,
    "waiting for components": WaitingForMaterialReason,
    "paste supply": WaitingForMaterialReason,  # Example
    "waiting for operator": WaitingForOperatorReason,
    "no operator": WaitingForOperatorReason,
    "waiting for upstream": WaitingForUpstreamReason,
    "upstream down": WaitingForUpstreamReason,
    "starved": WaitingForUpstreamReason,  # Often implies upstream issue
    "waiting for downstream": WaitingForDownstreamReason,
    "downstream down": WaitingForDownstreamReason,
    "blocked": WaitingForDownstreamReason,  # Often implies downstream issue
    "waiting": WaitingOtherReason,  # Generic waiting if no other detail
    # External
    "no demand": NoDemandReason,
    "no orders": NoDemandReason,
    "external issue": ExternalFactorReason,  # Utility, weather etc. if applicable
    # Quality/Speed (If they are the *reason* for the stop)
    "quality issue": QualityLossReason,
    "rejects": QualityLossReason,
    "slow speed": SpeedLossReason,  # Less common as a stop reason itself
    # Other/Unknown
    "unknown": UnknownReason,
    "not specified": UnknownReason,
    "ending order": ProcessReason,  # Or maybe OperationalPlannedReason? Let's use ProcessReason for now.
    "starting order": ProcessReason,  # Could also be part of Changeover?
}


def get_state_reason_instance(
    cls: Type[owl.Thing], description: Optional[str]
) -> Optional[owl.Thing]:
    """Gets or creates a shared instance for a state or reason class based on description."""
    if not description:
        return None

    # Use the class name and a sanitized description as the instance ID
    # Sanitize description to make a valid IRI fragment
    sanitized_desc = re.sub(r"[^\w\-]+", "_", description)
    instance_id = f"{cls.__name__}_{sanitized_desc}"

    # Use the cache to ensure only one instance per type/description is created
    instance = get_or_create_instance(
        cls,
        instance_id,
        properties={
            "description": description
        },  # Store original description on the instance
        use_cache=True,
    )
    return instance


def map_row_to_ontology(
    row_data: Dict[str, Any],
    equipment_sequence_overrides: Dict[str, Dict[str, Dict[str, Any]]],
    equipment_type_sequence_order: Dict[str, int],
) -> None:
    """Map a single preprocessed data row to ontology instances."""

    record_id_str = row_data.get("record_id_str", "UNKNOWN_RECORD")
    logger.debug(f"--- Mapping row {record_id_str} ---")

    try:
        # --- 1. Identify/Create Core Assets (Plant, Line, Equipment) ---
        plant_id = row_data.get("PLANT")
        line_name = row_data.get("LINE_NAME")
        equipment_id = row_data.get("EQUIPMENT_ID")  # Actual unique asset ID
        equipment_name = row_data.get("EQUIPMENT_NAME")  # Name like LINE_CasePacker
        equipment_base_type = row_data.get("EQUIPMENT_BASE_TYPE")  # Parsed: CasePacker
        row_level = row_data.get(
            "EQUIPMENT_TYPE"
        )  # Indicates 'Line' or 'Equipment' level data

        if not plant_id or not line_name or not equipment_name:
            logger.warning(
                f"Row {record_id_str}: Missing critical identifiers (Plant, LineName, EquipName). Skipping."
            )
            return

        # Create Plant
        plant_props = {
            "plantId": plant_id,
            "plantDescription": row_data.get(
                "PLANT_DESCRIPTION"
            ),  # Use description as name?
            "latitude": row_data.get("PLANT_LATITUDE"),
            "longitude": row_data.get("PLANT_LONGITUDE"),
            # Add other plant attributes: division, subdivision, etc.
        }
        plant = get_or_create_instance(Plant, f"Plant_{plant_id}", plant_props)

        # Create Country and link to Plant
        country_code = row_data.get("PLANT_COUNTRY")
        if country_code:
            country = get_or_create_instance(
                Country,
                f"Country_{country_code}",
                {
                    "countryCode": country_code,
                    "countryName": row_data.get("PLANT_COUNTRY_DESCRIPTION"),
                },
            )
            plant.locatedInCountry = [
                country
            ]  # Functional property update handled by helper

        # Create Strategic Location and link to Plant
        strat_loc_code = row_data.get("PLANT_STRATEGIC_LOCATION")
        if strat_loc_code:
            strat_loc = get_or_create_instance(
                StrategicLocation,
                f"StratLoc_{strat_loc_code}",
                {
                    "name": row_data.get(
                        "PLANT_STRATEGIC_LOCATION_DESCRIPTION"
                    )  # Assuming name property exists
                },
            )
            plant.hasStrategicLocation = [strat_loc]  # Functional

        # Create Focus Factory and link to Plant
        focus_factory_name = row_data.get("GH_FOCUSFACTORY")
        focus_factory = None
        if focus_factory_name:
            focus_factory = get_or_create_instance(
                FocusFactory,
                f"FocusFactory_{focus_factory_name}",
                {"focusFactoryName": focus_factory_name},
            )
            # Ensure relationship (helper handles appending unique for non-functional 'hasFocusFactory')
            plant.hasFocusFactory = [focus_factory]
            focus_factory.locatedInPlant = [plant]  # Functional inverse

        # Create Physical Area and link to Focus Factory (if exists) and Plant
        physical_area_name = row_data.get("PHYSICAL_AREA")
        physical_area = None
        if physical_area_name:
            physical_area = get_or_create_instance(
                PhysicalArea,
                f"Area_{physical_area_name}",
                {"areaName": physical_area_name},
            )
            if focus_factory:
                physical_area.partOfFocusFactory = [focus_factory]  # Functional
                focus_factory.hasArea = [
                    physical_area
                ]  # Non-functional inverse (append unique)
            else:
                # If no focus factory, maybe link area directly to plant? Depends on model needs.
                # physical_area.locatedInPlant = [plant] # Example
                pass

        # Create Line and link to Plant, FocusFactory, Area
        line_props = {
            "lineName": line_name,
            "locatedInPlant": plant,  # Functional link set via property dict
        }
        line = get_or_create_instance(Line, f"Line_{line_name}", line_props)
        if focus_factory:
            line.partOfFocusFactory = [focus_factory]  # Functional
        if physical_area:
            line.locatedInArea = [physical_area]  # Functional
            physical_area.hasLine = [line]  # Non-functional inverse (append unique)

        # Create Equipment - Use EQUIPMENT_ID as primary identifier if available
        # Fallback to EQUIPMENT_NAME if ID is missing.
        equip_instance_id_base = equipment_id if equipment_id else equipment_name
        if not equip_instance_id_base:
            logger.warning(
                f"Row {record_id_str}: Cannot identify equipment (missing ID and Name). Skipping."
            )
            return

        # Prevent clashes if ID is numeric but read as float (e.g., 273.0)
        if (
            isinstance(equip_instance_id_base, float)
            and equip_instance_id_base.is_integer()
        ):
            equip_instance_id_base = str(int(equip_instance_id_base))
        elif isinstance(equip_instance_id_base, float):
            equip_instance_id_base = str(
                equip_instance_id_base
            )  # Keep decimal if needed?

        equip_instance_id = f"Equipment_{equip_instance_id_base}"

        equip_props = {
            "equipmentId": equipment_id,  # Store original ID if exists
            "equipmentName": equipment_name,  # Store original name
            "equipmentBaseType": (
                equipment_base_type if equipment_base_type != "Unknown" else None
            ),  # Store parsed type
            "isPartOfLine": line,  # Functional link
            "equipmentModel": row_data.get("EQUIPMENT_MODEL"),
            # Add COMPLEXITY, MODEL etc.
        }
        equipment = get_or_create_instance(Equipment, equip_instance_id, equip_props)

        # Add sequence order (only if it's actual equipment, not a line-level record)
        # And only if base type was successfully parsed
        is_line_level_row = (row_level == "Line") or (equipment_name == line_name)
        if (
            not is_line_level_row
            and equipment_base_type
            and equipment_base_type != "Unknown"
        ):
            order = equipment_type_sequence_order.get(equipment_base_type)
            # Check for overrides
            if (
                line_name in equipment_sequence_overrides
                and equipment_base_type in equipment_sequence_overrides[line_name]
            ):
                override_order = equipment_sequence_overrides[line_name][
                    equipment_base_type
                ].get("order")
                if override_order is not None:
                    order = override_order

            if order is not None:
                equipment.sequenceOrder = order  # Functional

            # Apply sequence relationships (upstream/downstream) based on overrides
            # This requires instances to exist, so might be better done *after* processing all rows
            # Or look up potential neighbours during mapping (can be slow)
            # Let's try looking up neighbours now.
            if (
                line_name in equipment_sequence_overrides
                and equipment_base_type in equipment_sequence_overrides[line_name]
            ):
                config = equipment_sequence_overrides[line_name][equipment_base_type]

                # Find potential upstream neighbour instance on the same line
                upstream_type = config.get("upstream")
                if upstream_type:
                    # Search for equipment on the same line with that base type
                    # This is inefficient if done row-by-row. Consider post-processing step.
                    # Simple check for now:
                    for (
                        other_equip
                    ) in line.hasEquipment:  # Assumes hasEquipment is populated
                        if (
                            other_equip != equipment
                            and hasattr(other_equip, "equipmentBaseType")
                            and other_equip.equipmentBaseType == upstream_type
                        ):
                            equipment.isImmediatelyDownstreamOf = [
                                other_equip
                            ]  # Non-functional append unique
                            other_equip.isImmediatelyUpstreamOf = [
                                equipment
                            ]  # Non-functional append unique
                            break  # Assume only one immediate upstream for simplicity here

                # Find potential downstream neighbour instance
                downstream_type = config.get("downstream")
                if downstream_type:
                    for other_equip in line.hasEquipment:
                        if (
                            other_equip != equipment
                            and hasattr(other_equip, "equipmentBaseType")
                            and other_equip.equipmentBaseType == downstream_type
                        ):
                            equipment.isImmediatelyUpstreamOf = [
                                other_equip
                            ]  # Non-functional append unique
                            other_equip.isImmediatelyDownstreamOf = [
                                equipment
                            ]  # Non-functional append unique
                            break

        # --- 2. Create EventRecord ---
        # Use a unique ID, e.g., combining key identifiers and start time if available
        start_time_str = row_data.get(
            "JOB_START_TIME_LOC"
        )  # Use the LOC time as it's the basis for the record
        event_record_id = f"Event_{equip_instance_id_base}_{record_id_str}"  # Use original record ID for uniqueness

        event_props = {
            "occursAtPlant": plant,
            "occursOnLine": line,
            "involvesEquipment": equipment,  # Link to the specific equipment/line instance
            "rampUpFlag": row_data.get("RAMPUP_FLAG"),
            # AE Model Time Components (Floats, Minutes)
            "reportedDurationMinutes": row_data.get("TOTAL_TIME"),
            "businessExternalTimeMinutes": row_data.get("BUSINESS_EXTERNAL_TIME"),
            "plantAvailableTimeMinutes": row_data.get("PLANT_AVAILABLE_TIME"),
            "effectiveRuntimeMinutes": row_data.get("EFFECTIVE_RUNTIME"),
            "plantDecisionTimeMinutes": row_data.get("PLANT_DECISION_TIME"),
            "productionAvailableTimeMinutes": row_data.get("PRODUCTION_AVAILABLE_TIME"),
            "downtimeMinutes": row_data.get("DOWNTIME"),
            "runTimeMinutes": row_data.get("RUN_TIME"),
            "notEnteredTimeMinutes": row_data.get("NOT_ENTERED"),
            "waitingTimeMinutes": row_data.get("WAITING_TIME"),
            "plantExperimentationTimeMinutes": row_data.get("PLANT_EXPERIMENTATION"),
            "allMaintenanceTimeMinutes": row_data.get("ALL_MAINTENANCE"),
            "autonomousMaintenanceTimeMinutes": row_data.get("AUTONOMOUS_MAINTENANCE"),
            "plannedMaintenanceTimeMinutes": row_data.get("PLANNED_MAINTENANCE"),
            "changeoverDurationMinutes": row_data.get("CHANGEOVER_DURATION"),
            "cleaningSanitizationTimeMinutes": row_data.get(
                "CLEANING_AND_SANITIZATION"
            ),
            "lunchBreakTimeMinutes": row_data.get(
                "LUNCH_AND_BREAK"
            ),  # Assuming this is the total lunch/break
            "meetingTrainingTimeMinutes": row_data.get("MEETING_AND_TRAINING"),
            "noDemandTimeMinutes": row_data.get("NO_DEMAND"),
            # Production Quantities
            "goodProductionQty": row_data.get("GOOD_PRODUCTION_QTY"),
            "rejectProductionQty": row_data.get("REJECT_PRODUCTION_QTY"),
        }
        event_record = get_or_create_instance(EventRecord, event_record_id, event_props)

        # --- 3. Add TimeInterval (if valid times exist) ---
        start_time = parse_datetime_with_tz(row_data.get("JOB_START_TIME_LOC"))
        end_time = parse_datetime_with_tz(row_data.get("JOB_END_TIME_LOC"))

        if start_time and end_time:
            interval_id = f"Interval_{event_record_id}"
            interval = get_or_create_instance(
                TimeInterval,
                interval_id,
                {"startTime": start_time, "endTime": end_time},
            )
            event_record.occursDuring = [interval]  # Functional

            # Calculate duration in seconds
            duration_seconds = (end_time - start_time).total_seconds()
            event_record.calculatedDurationSeconds = duration_seconds  # Functional
        else:
            logger.warning(
                f"Row {record_id_str}: Missing or invalid JOB_START/END_TIME_LOC. Cannot create TimeInterval or calculate duration."
            )
            # event_record.calculatedDurationSeconds = None # Ensure it's None if not calculated

        # --- 4. Add Utilization State & Reason (using shared instances) ---
        state_desc_raw = row_data.get("UTIL_STATE_DESCRIPTION")
        reason_desc_raw = row_data.get("UTIL_REASON_DESCRIPTION")

        state_instance = None
        if state_desc_raw:
            state_desc_lower = state_desc_raw.lower()
            # Find corresponding class from map
            StateClass = UnknownState  # Default
            for keyword, Cls in STATE_CLASS_MAP.items():
                if keyword in state_desc_lower:
                    StateClass = Cls
                    break  # Take first match (adjust order in map if needed)

            state_instance = get_state_reason_instance(StateClass, state_desc_raw)
            if state_instance:
                event_record.hasState = [state_instance]  # Functional

        reason_instance = None
        if reason_desc_raw:
            reason_desc_lower = reason_desc_raw.lower()
            # Find corresponding class from map
            ReasonClass = UnknownReason  # Default
            # More specific matches first
            sorted_reason_keywords = sorted(
                REASON_CLASS_MAP.keys(), key=len, reverse=True
            )
            for keyword in sorted_reason_keywords:
                if keyword in reason_desc_lower:
                    ReasonClass = REASON_CLASS_MAP[keyword]
                    break

            reason_instance = get_state_reason_instance(ReasonClass, reason_desc_raw)
            if reason_instance:
                event_record.hasReason = [
                    reason_instance
                ]  # Non-functional append unique

        # --- 5. Add Process Context (Material, Order, Shift, Crew) ---
        material_id = row_data.get("MATERIAL_ID")
        if material_id:
            material = get_or_create_instance(
                Material,
                f"Material_{material_id}",
                {
                    "materialId": material_id,
                    "materialDescription": row_data.get(
                        "SHORT_MATERIAL_ID"
                    ),  # Or MATERIAL_DESC if exists
                    "materialUOM": row_data.get("MATERIAL_UOM"),
                    # Add SIZE_TYPE etc.
                },
            )
            event_record.processesMaterial = [material]  # Non-functional append unique

        order_id = row_data.get("PRODUCTION_ORDER_ID")
        if order_id:
            # Ensure order_id is string
            if isinstance(order_id, float) and order_id.is_integer():
                order_id = str(int(order_id))
            elif isinstance(order_id, float):
                order_id = str(order_id)

            order = get_or_create_instance(
                ProductionOrder,
                f"Order_{order_id}",
                {
                    "orderId": order_id,
                    "orderDescription": row_data.get("PRODUCTION_ORDER_DESC"),
                    "orderRate": row_data.get("PRODUCTION_ORDER_RATE"),
                    "orderRateUOM": row_data.get("PRODUCTION_ORDER_UOM"),
                },
            )
            event_record.relatesToOrder = [order]  # Non-functional append unique

        shift_name = row_data.get("SHIFT_NAME")
        if shift_name:
            shift = get_or_create_instance(
                Shift, f"Shift_{shift_name}", {"shiftName": shift_name}
            )
            event_record.duringShift = [shift]  # Functional

            crew_id = row_data.get("CREW_ID")
            if crew_id:
                crew = get_or_create_instance(
                    Crew, f"Crew_{crew_id}", {"crewId": crew_id}
                )
                event_record.operatedByCrew = [crew]  # Functional

        logger.debug(f"--- Successfully mapped row {record_id_str} ---")

    except Exception as e:
        logger.error(
            f"Error mapping row {record_id_str} to ontology: {e}", exc_info=True
        )
        # Decide whether to raise e or just log and continue
        # raise # Uncomment to stop execution on first error


# =============================================================================
# Query Functions (Examples)
# =============================================================================


def find_equipment_by_type(equipment_type: str) -> List[Equipment]:
    """Find equipment instances by their base type."""
    if not equipment_type:
        logger.warning("Cannot search for equipment with None/empty type")
        return []
    matching_equipment = list(
        onto.search(type=onto.Equipment, equipmentBaseType=equipment_type)
    )
    logger.debug(
        f"Found {len(matching_equipment)} instances of type '{equipment_type}'"
    )
    return matching_equipment


def find_downstream_equipment(equipment: Equipment) -> List[Equipment]:
    """Find equipment immediately downstream of the given equipment."""
    if not equipment:
        return []
    # isImmediatelyUpstreamOf property links an equipment to its downstream neighbours
    downstream = list(equipment.isImmediatelyUpstreamOf)
    logger.debug(f"Found {len(downstream)} downstream equipment for {equipment.name}")
    return downstream


def find_upstream_equipment(equipment: Equipment) -> List[Equipment]:
    """Find equipment immediately upstream of the given equipment."""
    if not equipment:
        return []
    # isImmediatelyDownstreamOf property links an equipment to its upstream neighbours
    upstream = list(equipment.isImmediatelyDownstreamOf)
    logger.debug(f"Found {len(upstream)} upstream equipment for {equipment.name}")
    return upstream


def find_events_by_reason_description(reason_desc_substring: str) -> List[EventRecord]:
    """Find events whose reason description contains a substring."""
    matching_events = []
    if not reason_desc_substring:
        return []

    # Search for Reason instances matching the description
    matching_reasons = list(
        onto.search(
            type=onto.UtilizationReason, description=f"*{reason_desc_substring}*"
        )
    )

    if not matching_reasons:
        logger.debug(
            f"No UtilizationReason instances found with description containing '{reason_desc_substring}'"
        )
        return []

    logger.debug(
        f"Found {len(matching_reasons)} reason instances matching '*{reason_desc_substring}*'. Searching for events..."
    )

    # Find events linked to these reasons
    for reason_instance in matching_reasons:
        # Find instances where 'hasReason' points to this reason_instance
        events_for_reason = list(onto.search(hasReason=reason_instance))
        matching_events.extend(events_for_reason)

    # Remove duplicates if an event somehow links to multiple matching reasons
    matching_events = list(set(matching_events))
    logger.debug(
        f"Found {len(matching_events)} events linked to reasons containing '{reason_desc_substring}'"
    )
    return matching_events


# =============================================================================
# Main Execution Block
# =============================================================================


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Manufacturing Ontology Builder")
    parser.add_argument("--input", "-i", required=True, help="Input CSV file path")
    settings = get_ontology_settings()
    default_output = settings.get(
        "default_output_file", "manufacturing_ontology_revised_populated.owl"
    )
    parser.add_argument(
        "--output", "-o", help="Output OWL file path", default=default_output
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )
    return parser.parse_args()


def main():
    """Main application entry point."""
    args = parse_arguments()
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))

    input_path = Path(args.input)
    if not input_path.exists():
        logger.critical(f"Input file not found: {input_path}")
        return 1

    try:
        # Load and preprocess
        df_raw = load_csv_data(args.input)
        processed_df = preprocess_manufacturing_data(df_raw)

        # Get configuration
        equipment_type_seq = get_equipment_type_sequence_order()
        equipment_seq_overrides = get_equipment_sequence_overrides()

        # --- Ontology Population ---
        stats = {"total_rows": len(processed_df), "processed_rows": 0, "error_rows": 0}
        logger.info(f"Populating ontology from {stats['total_rows']} processed rows...")
        row_count = len(processed_df)
        data_rows = processed_df.to_dict("records")  # More efficient for iteration

        # Wrap processing in ontology context
        with onto:
            for i, row_data in enumerate(data_rows):
                try:
                    map_row_to_ontology(
                        row_data, equipment_seq_overrides, equipment_type_seq
                    )
                    stats["processed_rows"] += 1
                except Exception as e:
                    # Error logged within map_row_to_ontology
                    stats["error_rows"] += 1

                # Log progress
                if (i + 1) % 1000 == 0 or (i + 1) == row_count:  # Log every 1000 rows
                    logger.info(
                        f"Mapped {i + 1}/{row_count} rows ({(i + 1) / row_count:.1%})"
                    )

        # Save ontology
        output_path = args.output
        output_format = settings.get("format", "rdfxml")
        logger.info(f"Saving ontology to {output_path} in format {output_format}")
        onto.save(file=output_path, format=output_format)

        # Optional: Run reasoner
        # logger.info("Synchronizing reasoner (this may take time)...")
        # try:
        #     with onto:
        #         owl.sync_reasoner() # Use Pellet or HermiT if configured
        #     logger.info("Reasoner synchronized successfully.")
        # except Exception as e:
        #     logger.warning(f"Could not synchronize reasoner: {e}")

        # Run example queries
        logger.info("--- Running Example Queries ---")
        case_packers = find_equipment_by_type("CasePacker")
        logger.info(f"Found {len(case_packers)} CasePacker equipment instances.")
        if case_packers:
            cp1 = case_packers[0]
            logger.info(f"Example CasePacker: {cp1.name}")
            upstream = find_upstream_equipment(cp1)
            downstream = find_downstream_equipment(cp1)
            logger.info(f"  Upstream: {[e.name for e in upstream]}")
            logger.info(f"  Downstream: {[e.name for e in downstream]}")

        jam_events = find_events_by_reason_description("Jam")  # Case-insensitive search
        logger.info(f"Found {len(jam_events)} events with 'Jam' in reason description.")

        # --- Final Statistics ---
        logger.info("--- Processing Summary ---")
        logger.info(f"Total rows in input: {stats['total_rows']}")
        logger.info(f"Rows processed for mapping: {stats['processed_rows']}")
        if stats["error_rows"] > 0:
            logger.warning(f"Rows with errors during mapping: {stats['error_rows']}")
        logger.info("---------------------------")

        logger.info("Processing completed.")
        return 0

    except Exception as e:
        logger.critical(
            f"An critical error occurred in the main process: {e}", exc_info=True
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
