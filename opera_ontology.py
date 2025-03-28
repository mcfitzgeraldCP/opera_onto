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

# =============================================================================
# Configuration
# =============================================================================


def get_ontology_settings() -> Dict[str, Any]:
    """Get general ontology settings."""
    return {
        "ontology_iri": "http://example.org/manufacturing_revised_ontology_v2.owl",  # Updated IRI Version
        "default_output_file": "manufacturing_ontology_revised_populated_v2.owl",  # Updated Output Version
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
    """Define line-specific equipment sequence overrides (order number)."""
    # Example overrides based on previous config examples
    # This now primarily affects the 'sequenceOrder' property value assignment.
    return {
        # Example: VIPCO012 might have a non-standard sequence order
        # "VIPCO012": {
        #     "TubeMaker": {"order": 1}, # Assuming TubeMaker is parsed type
        #     "CasePacker": {"order": 2},
        # },
        # Example: FIPCO006 skips Cartoner, direct Filler->CasePacker
        # "FIPCO006": {
        #     "Filler": {"order": 1},
        #     "CasePacker": {"order": 2}, # Use actual parsed types
        # },
        # Add actual overrides based on real line configurations
    }


# =============================================================================
# Ontology Definition (Core, Classes, Properties) - REVISED
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

    # --- Utilization States (REVISED based on AE Model) ---
    class UtilizationState(Thing):
        """The operational state of an asset during an EventRecord, aligned with AE Model categories."""

        pass

    class RuntimeState(UtilizationState):
        """State corresponding to AE Model category 'Runtime'."""

        pass

    class UnplannedState(UtilizationState):
        """State corresponding to AE Model category 'Unplanned'."""

        pass

    class WaitingState(UtilizationState):
        """State corresponding to AE Model category 'Waiting'."""

        pass

    class PlantDecisionState(UtilizationState):
        """State corresponding to AE Model category 'Plant Decision'."""

        pass

    class BusinessExternalState(UtilizationState):
        """State corresponding to AE Model category 'Business External'."""

        pass

    class UnknownAEState(UtilizationState):
        """State when the AE Model category could not be determined."""

        pass

    # --- Utilization Reasons (Hierarchy kept, but mapping from free text removed) ---
    class UtilizationReason(Thing):
        """The reason behind a specific UtilizationState. (Hierarchy retained for potential future use)."""

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
        pass

    class OperationalPlannedReason(PlannedReason):
        pass

    class LunchBreakReason(OperationalPlannedReason):
        pass

    class MeetingTrainingReason(OperationalPlannedReason):
        pass

    class ExperimentationReason(PlannedReason):
        pass

    # Reasons for Unplanned Stops (Downtime/Waiting)
    class UnplannedReason(UtilizationReason):
        pass

    class BreakdownReason(UnplannedReason):
        pass

    class JamReason(UnplannedReason):
        pass

    class AdjustmentReason(UnplannedReason):
        pass

    class ProcessReason(UnplannedReason):
        pass

    class WaitingReason(UnplannedReason):
        pass  # Maps to WaitingState now

    class WaitingForMaterialReason(WaitingReason):
        pass

    class WaitingForOperatorReason(WaitingReason):
        pass

    class WaitingForUpstreamReason(WaitingReason):
        pass

    class WaitingForDownstreamReason(WaitingReason):
        pass

    class WaitingOtherReason(WaitingReason):
        pass

    # Reasons for External Non-Availability
    class ExternalReason(UtilizationReason):
        pass

    class NoDemandReason(ExternalReason):
        pass

    class ExternalFactorReason(ExternalReason):
        pass

    # Other potential reasons
    class QualityLossReason(UtilizationReason):
        pass

    class SpeedLossReason(UtilizationReason):
        pass

    class UnknownReason(UtilizationReason):
        pass


# --- Property Definitions (REVISED) ---
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
        range = [Equipment]  # Event usually relates to one specific equip instance

    class hasState(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [UtilizationState]  # An event captures one AE state

    class hasReason(owl.ObjectProperty):  # Kept, but not populated from free text
        domain = [EventRecord]
        range = [UtilizationReason]
        # Non-functional allows linking if specific reasons *can* be identified later

    class occursDuring(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [TimeInterval]

    class processesMaterial(owl.ObjectProperty):
        domain = [EventRecord]
        range = [Material]  # Non-functional

    class relatesToOrder(owl.ObjectProperty):
        domain = [EventRecord]
        range = [ProductionOrder]  # Non-functional

    class duringShift(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [Shift]

    class operatedByCrew(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [Crew]

    # --- Asset Hierarchy & Location Relationships (INVERSES CORRECTED) ---

    # Focus Factory Relationships
    class locatedInPlant(owl.ObjectProperty, owl.FunctionalProperty):
        # Domain expanded to include FocusFactory
        domain = [Line, Equipment, PhysicalArea, FocusFactory]
        range = [Plant]
        # Inverse will be defined on Plant (e.g., plantContains) if needed, or managed via FF's inverse

    class hasFocusFactory(owl.ObjectProperty):  # Plant -> FocusFactory
        domain = [Plant]
        range = [FocusFactory]
        # inverse_property = locatedInPlant # CORRECTED: Inverse defined on FocusFactory instead

    class partOfFocusFactory(
        owl.ObjectProperty, owl.FunctionalProperty
    ):  # Area/Line/Equip -> FocusFactory
        domain = [PhysicalArea, Line, Equipment]
        range = [FocusFactory]
        # Inverse defined below

    # Define inverses on FocusFactory
    class ffHasArea(owl.ObjectProperty):
        domain = [FocusFactory]
        range = [PhysicalArea]
        inverse_property = partOfFocusFactory

    class ffHasLine(owl.ObjectProperty):
        domain = [FocusFactory]
        range = [Line]
        inverse_property = partOfFocusFactory

    class ffHasEquipment(owl.ObjectProperty):
        domain = [FocusFactory]
        range = [Equipment]
        inverse_property = partOfFocusFactory

    # Also set inverse for hasFocusFactory
    locatedInPlant.inverse_property = hasFocusFactory  # FF -> Plant inverse

    # Physical Area Relationships
    class hasArea(owl.ObjectProperty):  # FocusFactory -> Area (Now use ffHasArea)
        # This might be redundant now, consider removing if ffHasArea covers it. Keep for now.
        domain = [FocusFactory]
        range = [PhysicalArea]
        inverse_property = partOfFocusFactory  # Okay

    class locatedInArea(
        owl.ObjectProperty, owl.FunctionalProperty
    ):  # Line/Equip -> Area
        domain = [Line, Equipment]
        range = [PhysicalArea]
        # Inverse defined below

    # Define inverses on PhysicalArea
    class areaHasLine(owl.ObjectProperty):
        domain = [PhysicalArea]
        range = [Line]
        inverse_property = locatedInArea

    class areaHasEquipment(owl.ObjectProperty):
        domain = [PhysicalArea]
        range = [Equipment]
        inverse_property = locatedInArea

    # Line Relationships
    class hasLine(owl.ObjectProperty):  # PhysicalArea -> Line (Now use areaHasLine)
        # This might be redundant now, consider removing if areaHasLine covers it. Keep for now.
        domain = [PhysicalArea]
        range = [Line]
        inverse_property = locatedInArea  # Okay

    class isPartOfLine(owl.ObjectProperty, owl.FunctionalProperty):  # Equip -> Line
        domain = [Equipment]
        range = [Line]
        # inverse_property = hasLine # CORRECTED below

    # Equipment Relationships
    class hasEquipment(owl.ObjectProperty):  # Line -> Equip
        domain = [Line]
        range = [Equipment]
        inverse_property = isPartOfLine  # CORRECT

    # Correct inverse for isPartOfLine
    isPartOfLine.inverse_property = hasEquipment  # CORRECT

    # Other Location Relationships
    class locatedInCountry(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Plant]
        range = [Country]

    class hasStrategicLocation(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Plant]
        range = [StrategicLocation]

    # Equipment Sequence Relationships
    class isImmediatelyUpstreamOf(owl.ObjectProperty):
        domain = [Equipment]
        range = [Equipment]
        # Non-functional, inverse defined below

    class isImmediatelyDownstreamOf(owl.ObjectProperty):
        domain = [Equipment]
        range = [Equipment]
        inverse_property = isImmediatelyUpstreamOf  # CORRECT

    # Organizational Relationships (Example - check if inverses needed/correct)
    class partOfDivision(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Plant, FocusFactory]
        range = [Division]

    class partOfSubDivision(owl.ObjectProperty, owl.FunctionalProperty):
        domain = [Plant, FocusFactory]
        range = [SubDivision]

    # --- Data Properties (Attributes) ---

    # TimeInterval Properties
    class startTime(owl.DataProperty, owl.FunctionalProperty):
        domain = [TimeInterval]
        range = [datetime]

    class endTime(owl.DataProperty, owl.FunctionalProperty):
        domain = [TimeInterval]
        range = [datetime]

    # Plant Properties
    class plantId(owl.DataProperty, owl.FunctionalProperty):
        domain = [Plant]
        range = [str]

    class plantDescription(owl.DataProperty):
        domain = [Plant]
        range = [str]

    class latitude(owl.DataProperty, owl.FunctionalProperty):
        domain = [Plant]
        range = [float]

    class longitude(owl.DataProperty, owl.FunctionalProperty):
        domain = [Plant]
        range = [float]

    # Country Properties
    class countryCode(owl.DataProperty, owl.FunctionalProperty):
        domain = [Country]
        range = [str]

    class countryName(owl.DataProperty, owl.FunctionalProperty):
        domain = [Country]
        range = [str]

    # StrategicLocation Property (NEW)
    class strategicLocationName(owl.DataProperty, owl.FunctionalProperty):
        domain = [StrategicLocation]
        range = [str]

    # Line Properties
    class lineName(owl.DataProperty, owl.FunctionalProperty):
        domain = [Line]
        range = [str]

    # Equipment Properties
    class equipmentId(owl.DataProperty, owl.FunctionalProperty):
        domain = [Equipment]
        range = [str]

    class equipmentName(owl.DataProperty, owl.FunctionalProperty):
        domain = [Equipment]
        range = [str]

    class equipmentBaseType(owl.DataProperty, owl.FunctionalProperty):
        domain = [Equipment]
        range = [str]

    class equipmentModel(owl.DataProperty):
        domain = [Equipment]
        range = [str]

    class sequenceOrder(owl.DataProperty, owl.FunctionalProperty):
        domain = [Equipment]
        range = [int]

    # FocusFactory, Area, Org Properties
    class focusFactoryName(owl.DataProperty, owl.FunctionalProperty):
        domain = [FocusFactory]
        range = [str]

    class areaName(owl.DataProperty, owl.FunctionalProperty):
        domain = [PhysicalArea]
        range = [str]

    class divisionName(owl.DataProperty, owl.FunctionalProperty):
        domain = [Division]
        range = [str]

    class subdivisionName(owl.DataProperty, owl.FunctionalProperty):
        domain = [SubDivision]
        range = [str]

    # Material Properties
    class materialId(owl.DataProperty, owl.FunctionalProperty):
        domain = [Material]
        range = [str]

    class materialDescription(owl.DataProperty):
        domain = [Material]
        range = [str]

    class materialUOM(owl.DataProperty, owl.FunctionalProperty):
        domain = [Material]
        range = [str]

    # Production Order Properties
    class orderId(owl.DataProperty, owl.FunctionalProperty):
        domain = [ProductionOrder]
        range = [str]

    class orderDescription(owl.DataProperty):
        domain = [ProductionOrder]
        range = [str]

    class orderRate(owl.DataProperty, owl.FunctionalProperty):
        domain = [ProductionOrder]
        range = [float]

    class orderRateUOM(owl.DataProperty, owl.FunctionalProperty):
        domain = [ProductionOrder]
        range = [str]

    # Shift/Crew Properties
    class shiftName(owl.DataProperty, owl.FunctionalProperty):
        domain = [Shift]
        range = [str]

    class crewId(owl.DataProperty, owl.FunctionalProperty):
        domain = [Crew]
        range = [str]

    # EventRecord Properties
    class calculatedDurationSeconds(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class reportedDurationMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class rampUpFlag(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [bool]

    # NEW: Raw descriptions captured on EventRecord
    class rawStateDescription(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [str]

    class rawReasonDescription(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [str]

    # AE Model Time Components (All Functional Floats on EventRecord)
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
        range = [float]  # Corresponds to 'Unplanned' AE category total?

    class runTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # Corresponds to 'Runtime' AE category total?

    class notEnteredTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # Part of 'Unplanned'?

    class waitingTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # Corresponds to 'Waiting' AE category total?

    # Note: Some time properties below might map conceptually *within* AE categories (e.g., Maintenance within Plant Decision/Unplanned)
    # Keep them as distinct properties on EventRecord for detailed data capture.
    class plantExperimentationTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class allMaintenanceTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class autonomousMaintenanceTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class plannedMaintenanceTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class changeoverDurationMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class cleaningSanitizationTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class lunchBreakTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class meetingTrainingTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class noDemandTimeMinutes(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]  # Part of 'Business External'?

    # Production Quantities
    class goodProductionQty(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    class rejectProductionQty(owl.DataProperty, owl.FunctionalProperty):
        domain = [EventRecord]
        range = [float]

    # REMOVED: stateDescription, reasonDescription from UtilizationState/Reason classes

    # UtilizationReason Properties (Kept for potential future use of hierarchy)
    class reasonDescription(
        owl.DataProperty
    ):  # Keep property definition, but don't populate from free text
        domain = [UtilizationReason]
        range = [str]


# =============================================================================
# Utility Functions (Largely Unchanged)
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
        if " " in timestamp_str and ("+" in timestamp_str or "-" in timestamp_str[-6:]):
            parts = timestamp_str.rsplit(" ", 1)
            dt_part_str = parts[0]
            tz_part_str = parts[1]

            if ":" in tz_part_str:
                tz_part_str = tz_part_str.replace(":", "")

            if not (
                len(tz_part_str) == 5
                and tz_part_str[0] in ("+", "-")
                and tz_part_str[1:].isdigit()
            ):
                raise ValueError("Timezone offset not in +/-HHMM format")

            timestamp_to_parse = f"{dt_part_str}{tz_part_str}"
            if "." in dt_part_str:
                format_str = "%Y-%m-%d %H:%M:%S.%f%z"
            else:
                format_str = "%Y-%m-%d %H:%M:%S%z"  # Handle cases without milliseconds

            dt_obj = datetime.strptime(timestamp_to_parse, format_str)
            return dt_obj
        else:
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
        try:
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

    prefix = f"{line_name}_"
    if equipment_name.startswith(prefix):
        base_type_part = equipment_name[len(prefix) :]
        base_type = re.sub(
            r"\d+$", "", base_type_part
        )  # Remove potential trailing numbers

        if base_type:
            logger.debug(
                f"Parsed equipment type '{base_type}' from '{equipment_name}' using line '{line_name}'"
            )
            return base_type
        else:
            logger.warning(
                f"Equipment name '{equipment_name}' matches prefix '{prefix}' but has no type part."
            )
            return "Unknown"

    known_types_lower = {t.lower(): t for t in get_equipment_type_sequence_order()}
    if equipment_name.lower() in known_types_lower:
        base_type = known_types_lower[equipment_name.lower()]
        logger.debug(
            f"Equipment name '{equipment_name}' directly matched known type '{base_type}'."
        )
        return base_type

    if "_" in equipment_name:
        possible_type_part = equipment_name.split("_")[-1]
        base_type = re.sub(r"\d+$", "", possible_type_part)
        if base_type:
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
    return cleaned if cleaned else None


def clean_numeric_value(value: Any) -> Optional[float]:
    """Clean numeric values, handling None/NaN/empty strings, return float or None."""
    if pd.isna(value) or value is None or value == "":
        return None
    try:
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
# Ontology Helper Functions (REVISED)
# =============================================================================

# Cache for shared instances (like AE states)
_shared_instances_cache = {}


def get_or_create_instance(
    cls: Type[owl.Thing],
    instance_id: str,
    properties: Optional[Dict[str, Any]] = None,
    namespace: owl.Namespace = onto,
    use_cache: bool = False,  # Flag primarily for AE state instances
) -> owl.Thing:
    """
    Get existing instance by identifier or create a new one.
    Handles functional properties by overwriting, non-functional by appending unique.
    Uses a cache for specific classes if use_cache=True.
    """
    if not instance_id or not isinstance(instance_id, str):
        raise ValueError(
            f"Invalid instance_id provided for class {cls.__name__}: {instance_id}"
        )

    # Sanitize ID for IRI - replace non-word chars (excluding hyphen) with underscore
    sanitized_id = re.sub(r"[^\w\-]+", "_", instance_id)
    # Prevent IDs starting with numbers if using certain RDF formats
    if sanitized_id and sanitized_id[0].isdigit():  # Added check for empty string
        sanitized_id = f"_{sanitized_id}"

    # Handle potential empty sanitized_id after sanitization
    if not sanitized_id:
        raise ValueError(
            f"Sanitized instance_id became empty for original ID '{instance_id}' and class {cls.__name__}"
        )

    instance_iri = f"{namespace.base_iri}{sanitized_id}"

    instance = None
    cache_key = (cls, sanitized_id)  # Use class and sanitized ID for cache key

    if use_cache and cache_key in _shared_instances_cache:
        instance = _shared_instances_cache[cache_key]
        # logger.debug(f"Retrieved '{sanitized_id}' of class {cls.__name__} from cache.") # Can be noisy
    else:
        # Search in the world associated with the namespace
        instance = namespace.world.search_one(iri=instance_iri)
        if instance is not None:
            # Check if the found instance is of the expected class type
            if not isinstance(instance, cls):
                # Check superclass compatibility (more robust check)
                instance_class = instance.__class__
                expected_class = cls
                # Check MRO (Method Resolution Order) for flexibility
                if not any(c == expected_class for c in instance_class.mro()):
                    raise TypeError(
                        f"IRI conflict: Found existing instance <{instance_iri}> of type {instance_class.__name__}, not compatible with expected type {expected_class.__name__} (not in MRO)."
                    )
                # If compatible, use existing
            # else: # Instance is of the correct type or a subclass, which is okay
            #     logger.debug(f"Retrieved existing instance '{sanitized_id}' of class {cls.__name__} from ontology.")
            pass  # Use the retrieved instance
        else:
            # logger.debug(f"Creating new instance '{sanitized_id}' of class {cls.__name__}.")
            instance = cls(sanitized_id, namespace=namespace)

        if use_cache:  # Add to cache whether found or newly created
            _shared_instances_cache[cache_key] = instance
            # logger.debug(f"Stored/Updated '{sanitized_id}' of class {cls.__name__} in cache.")

    # Assign properties if provided
    if properties:
        for prop_name, value in properties.items():
            if value is None:  # Skip None values explicitly
                continue

            try:
                # --- MODIFIED PROPERTY LOOKUP & VALIDATION ---
                prop = None  # Initialize prop
                try:
                    prop = onto[prop_name]  # Use dictionary-style lookup
                    # --- ADD DEBUG LOGGING ---
                    logger.debug(
                        f"For prop_name '{prop_name}', onto[...] lookup returned: {prop} (type: {type(prop)})"
                    )
                    # --- END DEBUG LOGGING ---
                except KeyError:
                    logger.warning(
                        f"Property '{prop_name}' not found via dictionary lookup (KeyError) for class {cls.__name__}. Skipping assignment for instance {instance.name}."
                    )
                    continue

                is_prop_instance = isinstance(prop, owl.Property)
                is_prop_subclass = False
                if prop is not None and isinstance(
                    prop, type
                ):  # Check if prop is a class type
                    try:
                        # Check if it's a subclass of owl.Property
                        is_prop_subclass = issubclass(prop, owl.Property)
                    except TypeError:
                        # issubclass() arg 1 must be a class
                        pass  # is_prop_subclass remains False

                logger.debug(
                    f"Property '{prop_name}': is_instance={is_prop_instance}, is_subclass={is_prop_subclass}"
                )

                # Check if it's a valid property (either instance or subclass)
                if not is_prop_instance and not is_prop_subclass:
                    logger.warning(
                        f"Property '{prop_name}' resolved to something ({type(prop)}) that is neither an instance nor a subclass of owl.Property for class {cls.__name__}. Skipping assignment for instance {instance.name}."
                    )
                    continue
                # --- END MODIFIED LOOKUP & VALIDATION ---

                # --- Determine if Functional (Works for both class and instance) ---
                # Check the MRO (Method Resolution Order) for the FunctionalProperty mixin
                prop_mro_check_target = (
                    prop if isinstance(prop, type) else prop.__class__
                )
                is_functional = owl.FunctionalProperty in prop_mro_check_target.mro()
                logger.debug(
                    f"Property '{prop_name}' determined as functional? {is_functional}"
                )
                # --- End Functional Check ---

                # --- Property Assignment Logic (Largely unchanged, uses setattr) ---
                if is_functional:
                    actual_value_to_set = (
                        value[0] if isinstance(value, list) and value else value
                    )
                    if isinstance(value, list) and len(value) > 1:
                        logger.warning(
                            f"Assigning only first value to functional property '{prop_name}' on {instance.name}"
                        )

                    current_direct_val = getattr(instance, prop_name, None)
                    if current_direct_val != actual_value_to_set:
                        setattr(instance, prop_name, actual_value_to_set)
                        # logger.debug(f"Set functional property '{prop_name}' on {instance.name}")

                else:  # Non-functional
                    current_list = list(getattr(instance, prop_name, []))
                    values_to_add = value if isinstance(value, list) else [value]

                    updated_list = list(current_list)
                    newly_added_count = 0
                    for val_item in values_to_add:
                        # Ensure we don't add duplicates
                        if val_item is not None:
                            # Need careful comparison, especially for OWL individuals
                            is_duplicate = False
                            for existing_item in updated_list:
                                if val_item == existing_item:
                                    is_duplicate = True
                                    break
                            if not is_duplicate:
                                updated_list.append(val_item)
                                newly_added_count += 1

                    if newly_added_count > 0:
                        setattr(instance, prop_name, updated_list)
                        # logger.debug(f"Added {newly_added_count} item(s) to non-functional property '{prop_name}' on {instance.name}")

            except AttributeError as ae:
                logger.error(
                    f"AttributeError processing property '{prop_name}' on {instance.name}. Error: {ae}",
                    exc_info=False,
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error setting property '{prop_name}' on instance {instance.name} with value '{value}': {e}",
                    exc_info=True,
                )

    return instance


# --- NEW Helper for AE State Instances ---
def get_ae_state_instance(
    ae_category_name: str, StateClass: Type[UtilizationState]
) -> UtilizationState:
    """
    Gets or creates a shared, cached instance for an AE UtilizationState class.
    The instance ID is derived from the class name and AE category name.
    No description is stored on the state instance itself.
    """
    if not ae_category_name or not StateClass:
        raise ValueError("Valid AE category name and StateClass are required.")

    # Create a clean ID, e.g., UnplannedState_Unplanned
    # Sanitize the category name just in case
    sanitized_category = re.sub(r"[^\w\-]+", "_", ae_category_name)
    instance_id = f"{StateClass.__name__}_{sanitized_category}"

    # Use get_or_create_instance with caching, but no properties
    instance = get_or_create_instance(
        cls=StateClass,
        instance_id=instance_id,
        properties=None,  # Important: Do not store descriptions here
        use_cache=True,
    )
    return instance


# =============================================================================
# Data Handling Functions (Load, Preprocess, Map - REVISED)
# =============================================================================


def load_csv_data(csv_path: str) -> pd.DataFrame:
    """Load data from CSV file."""
    logger.info(f"Loading data from {csv_path}")
    try:
        # Specify dtype for potential ID columns to avoid mixed type warnings if possible
        # Adjust based on actual data - this is a guess
        dtype_spec = {
            "EQUIPMENT_ID": str,
            "PRODUCTION_ORDER_ID": str,
            "MATERIAL_ID": str,
            "SHORT_MATERIAL_ID": str,
            "PLANT": str,
            "LINE_NAME": str,
            "EQUIPMENT_NAME": str,
            "CREW_ID": str,
            # Add others known to be strings or specific types
        }
        df = pd.read_csv(csv_path, low_memory=False, dtype=dtype_spec)
        # Add a unique record ID for easier instance naming/debugging
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

    # Define column types for cleaning
    # Ensure AE_MODEL_CATEGORY is treated as a key string identifier
    id_cols = [
        "EQUIPMENT_ID",
        "PRODUCTION_ORDER_ID",
        "MATERIAL_ID",
        "SHORT_MATERIAL_ID",
        "PLANT",
        "LINE_NAME",
        "EQUIPMENT_NAME",
        "CREW_ID",
        "AE_MODEL_CATEGORY",  # Treat as key identifier string
        "UTIL_STATE_DESCRIPTION",  # Will be captured as raw text
        "UTIL_REASON_DESCRIPTION",  # Will be captured as raw text
        "EQUIPMENT_TYPE",  # Row level 'Line' or 'Equipment'
        # Add other categorical/ID-like string columns here
        "PLANT_COUNTRY",
        "PLANT_STRATEGIC_LOCATION",
        "GH_FOCUSFACTORY",
        "PHYSICAL_AREA",
        "SHIFT_NAME",
        "MATERIAL_UOM",
        "PRODUCTION_ORDER_UOM",
    ]
    boolean_cols = ["RAMPUP_FLAG"]
    numeric_cols = [
        "TOTAL_TIME",
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
        "BREAK",
        "MEETING_AND_TRAINING",
        "NO_DEMAND",
        "PRIMARY_CONV_FACTOR",
        "PRODUCTION_ORDER_RATE",
        "SHIFT_DURATION_MIN",
        "PLANT_LATITUDE",
        "PLANT_LONGITUDE",
        "CHANGEOVER_COUNT",
        # UOM_ST, UOM_ST_SAP, TP_UOM - check if numeric or string codes
    ]
    datetime_cols = [  # Columns to be parsed later
        "JOB_START_TIME_LOC",
        "JOB_END_TIME_LOC",
        # Add others like SHIFT_START/END if they are full datetime strings
    ]

    # Clean String/ID columns
    for col in id_cols:
        if col in processed_df.columns:
            processed_df[col] = processed_df[col].apply(clean_string_value)
            # logger.debug(f"Cleaned string/ID column: {col}")

    # Clean Boolean columns
    for col in boolean_cols:
        if col in processed_df.columns:
            processed_df[col] = processed_df[col].apply(clean_boolean_value)
            # logger.debug(f"Cleaned boolean column: {col}")

    # Clean Numeric columns
    for col in numeric_cols:
        if col in processed_df.columns:
            processed_df[col] = processed_df[col].apply(clean_numeric_value)
            # logger.debug(f"Cleaned numeric column: {col}")

    # Clean remaining unspecified columns as general strings (descriptions etc.)
    all_cols = set(processed_df.columns)
    handled_cols = (
        set(id_cols)
        | set(boolean_cols)
        | set(numeric_cols)
        | set(datetime_cols)
        | {"record_id_str"}
    )
    other_string_cols = list(all_cols - handled_cols)
    for col in other_string_cols:
        if col in processed_df.columns:
            # Assume remaining are descriptive strings unless known otherwise
            processed_df[col] = processed_df[col].apply(clean_string_value)
            # logger.debug(f"Cleaned potential string column: {col}")

    # --- Extract Equipment Base Type ---
    logger.info("Extracting Equipment Base Type from EQUIPMENT_NAME...")
    if "EQUIPMENT_NAME" in processed_df.columns and "LINE_NAME" in processed_df.columns:
        processed_df["EQUIPMENT_BASE_TYPE"] = processed_df.apply(
            lambda row: parse_equipment_base_type(
                row["EQUIPMENT_NAME"], row["LINE_NAME"]
            ),
            axis=1,
        )
        logger.info("Finished extracting Equipment Base Type.")
        parsed_counts = processed_df["EQUIPMENT_BASE_TYPE"].value_counts()
        logger.info(f"Equipment Base Type parsing results:\n{parsed_counts}")
    else:
        logger.warning(
            "Missing EQUIPMENT_NAME or LINE_NAME. Cannot extract equipment base type."
        )
        if "EQUIPMENT_BASE_TYPE" not in processed_df.columns:
            processed_df["EQUIPMENT_BASE_TYPE"] = "Unknown"

    # --- Final Checks ---
    # Check if key columns for mapping exist
    required_cols = ["AE_MODEL_CATEGORY", "PLANT", "LINE_NAME", "EQUIPMENT_NAME"]
    missing_req = [
        col
        for col in required_cols
        if col not in processed_df.columns or processed_df[col].isnull().all()
    ]
    if missing_req:
        logger.error(
            f"CRITICAL: Missing required columns or columns entirely null after preprocessing: {missing_req}. Mapping will likely fail."
        )
        # Consider raising an error here depending on desired robustness
        # raise ValueError(f"Missing critical data columns for ontology mapping: {missing_req}")

    logger.info("Preprocessing finished.")
    return processed_df


# --- State Mapping Logic (REVISED) ---

# Map AE_MODEL_CATEGORY values (lowercase, stripped) to Ontology Classes
# Assumes AE_MODEL_CATEGORY contains values like 'Runtime', 'Unplanned', 'Waiting', etc.
AE_CATEGORY_CLASS_MAP = {
    "runtime": onto.RuntimeState,
    "unplanned": onto.UnplannedState,
    "waiting": onto.WaitingState,
    "plant decision": onto.PlantDecisionState,
    "business external": onto.BusinessExternalState,
    # Add mappings for None or specific codes if they represent unknown/other
    # If AE_MODEL_CATEGORY can be None/NaN, map to UnknownAEState
}

# REMOVED: STATE_CLASS_MAP, REASON_CLASS_MAP
# REMOVED: get_state_reason_instance (replaced by get_ae_state_instance used internally)


def map_row_to_ontology(
    row_data: Dict[str, Any],
    # sequence overrides only affect sequenceOrder value now
    equipment_sequence_overrides: Dict[str, Dict[str, Dict[str, Any]]],
    equipment_type_sequence_order: Dict[str, int],
) -> None:
    """Map a single preprocessed data row to ontology instances."""

    record_id_str = row_data.get("record_id_str", "UNKNOWN_RECORD")
    # logger.debug(f"--- Mapping row {record_id_str} ---") # Can be noisy

    try:
        # --- 1. Identify/Create Core Assets (Plant, Line, Equipment) ---
        plant_id = row_data.get("PLANT")
        line_name = row_data.get("LINE_NAME")
        equipment_id = row_data.get("EQUIPMENT_ID")  # Actual unique asset ID
        equipment_name = row_data.get("EQUIPMENT_NAME")  # Name like LINE_CasePacker
        equipment_base_type = row_data.get("EQUIPMENT_BASE_TYPE")  # Parsed: CasePacker
        row_level = row_data.get("EQUIPMENT_TYPE")  # Indicates 'Line' or 'Equipment'

        if not plant_id or not line_name or not equipment_name:
            logger.warning(
                f"Row {record_id_str}: Missing critical identifiers (Plant, LineName, EquipName). Skipping."
            )
            return

        # --- Create Hierarchy (Plant, Country, StratLoc, FF, Area, Line, Equip) ---
        # (Using get_or_create_instance helper)

        plant = get_or_create_instance(
            onto.Plant,
            f"Plant_{plant_id}",
            {
                "plantId": plant_id,
                "plantDescription": row_data.get("PLANT_DESCRIPTION"),
                "latitude": row_data.get("PLANT_LATITUDE"),
                "longitude": row_data.get("PLANT_LONGITUDE"),
            },
        )

        country_code = row_data.get("PLANT_COUNTRY")
        if country_code:
            country = get_or_create_instance(
                onto.Country,
                f"Country_{country_code}",
                {
                    "countryCode": country_code,
                    "countryName": row_data.get("PLANT_COUNTRY_DESCRIPTION"),
                },
            )
            plant.locatedInCountry = country  # Functional

        strat_loc_code = row_data.get("PLANT_STRATEGIC_LOCATION")
        if strat_loc_code:
            # Assuming name property exists or use code as name
            strat_loc = get_or_create_instance(
                onto.StrategicLocation,
                f"StratLoc_{strat_loc_code}",
                {
                    "strategicLocationName": row_data.get(
                        "PLANT_STRATEGIC_LOCATION_DESCRIPTION", strat_loc_code
                    )
                },
            )
            plant.hasStrategicLocation = strat_loc  # Functional

        focus_factory_name = row_data.get("GH_FOCUSFACTORY")
        focus_factory = None
        if focus_factory_name:
            focus_factory = get_or_create_instance(
                onto.FocusFactory,
                f"FocusFactory_{focus_factory_name}",
                {
                    "focusFactoryName": focus_factory_name,
                    "locatedInPlant": plant,  # Functional inverse link
                },
            )
            # Link Plant -> FF (Non-functional) - CORRECTED APPEND LOGIC
            current_ff_on_plant = list(getattr(plant, "hasFocusFactory", []))
            if focus_factory not in current_ff_on_plant:
                current_ff_on_plant.append(focus_factory)
                plant.hasFocusFactory = current_ff_on_plant  # Assign updated list

        physical_area_name = row_data.get("PHYSICAL_AREA")
        physical_area = None
        if physical_area_name:
            area_props = {"areaName": physical_area_name}
            if focus_factory:
                area_props["partOfFocusFactory"] = focus_factory  # Functional link
            # else link area directly to plant?
            # area_props["locatedInPlant"] = plant # Example if needed
            physical_area = get_or_create_instance(
                onto.PhysicalArea, f"Area_{physical_area_name}", area_props
            )
            # Link FF -> Area (Non-functional) - CORRECTED APPEND LOGIC
            if focus_factory:  # Ensure focus_factory exists
                current_area_on_ff = list(getattr(focus_factory, "ffHasArea", []))
                if physical_area not in current_area_on_ff:
                    current_area_on_ff.append(physical_area)
                    focus_factory.ffHasArea = current_area_on_ff  # Assign updated list

        line = get_or_create_instance(
            onto.Line,
            f"Line_{line_name}",
            {
                "lineName": line_name,
                "locatedInPlant": plant,  # Functional
                "partOfFocusFactory": focus_factory,  # Functional (None if no FF)
                "locatedInArea": physical_area,  # Functional (None if no Area)
            },
        )
        # Add inverse links from Area/FF to Line (Non-functional) - CORRECTED APPEND LOGIC
        if physical_area:
            current_line_on_area = list(getattr(physical_area, "areaHasLine", []))
            if line not in current_line_on_area:
                current_line_on_area.append(line)
                physical_area.areaHasLine = current_line_on_area  # Assign updated list
        if focus_factory:
            current_line_on_ff = list(getattr(focus_factory, "ffHasLine", []))
            if line not in current_line_on_ff:
                current_line_on_ff.append(line)
                focus_factory.ffHasLine = current_line_on_ff  # Assign updated list

        # Equipment instance ID logic (handle potential float IDs)
        equip_instance_id_base = equipment_id if equipment_id else equipment_name
        if not equip_instance_id_base:
            logger.warning(
                f"Row {record_id_str}: Cannot identify equipment (missing ID and Name). Skipping."
            )
            return
        if (
            isinstance(equip_instance_id_base, float)
            and equip_instance_id_base.is_integer()
        ):
            equip_instance_id_base = str(int(equip_instance_id_base))
        elif not isinstance(equip_instance_id_base, str):
            equip_instance_id_base = str(equip_instance_id_base)

        equip_instance_id = f"Equipment_{equip_instance_id_base}"

        equipment = get_or_create_instance(
            onto.Equipment,
            equip_instance_id,
            {
                "equipmentId": equipment_id,
                "equipmentName": equipment_name,
                "equipmentBaseType": (
                    equipment_base_type if equipment_base_type != "Unknown" else None
                ),
                "isPartOfLine": line,  # Functional link
                "locatedInArea": physical_area,  # Functional link (redundant via line?)
                "partOfFocusFactory": focus_factory,  # Functional link (redundant via line?)
                "equipmentModel": row_data.get("EQUIPMENT_MODEL"),
            },
        )
        # Add inverse links from Line/Area/FF to Equipment (Non-functional) - CORRECTED APPEND LOGIC
        current_equip_on_line = list(getattr(line, "hasEquipment", []))
        if equipment not in current_equip_on_line:
            current_equip_on_line.append(equipment)
            line.hasEquipment = current_equip_on_line  # Assign updated list

        if physical_area:
            current_equip_on_area = list(getattr(physical_area, "areaHasEquipment", []))
            if equipment not in current_equip_on_area:
                current_equip_on_area.append(equipment)
                physical_area.areaHasEquipment = (
                    current_equip_on_area  # Assign updated list
                )

        if focus_factory:
            current_equip_on_ff = list(getattr(focus_factory, "ffHasEquipment", []))
            if equipment not in current_equip_on_ff:
                current_equip_on_ff.append(equipment)
                focus_factory.ffHasEquipment = (
                    current_equip_on_ff  # Assign updated list
                )

        # Assign sequence order (considers overrides)
        is_line_level_row = (row_level == "Line") or (equipment_name == line_name)
        if (
            not is_line_level_row
            and equipment_base_type
            and equipment_base_type != "Unknown"
        ):
            order = equipment_type_sequence_order.get(equipment_base_type)
            if (
                line_name in equipment_sequence_overrides
                and equipment_base_type in equipment_sequence_overrides[line_name]
            ):
                override_order = equipment_sequence_overrides[line_name][
                    equipment_base_type
                ].get("order")
                if override_order is not None:
                    order = int(override_order)  # Ensure integer

            if order is not None:
                equipment.sequenceOrder = order  # Functional

        # --- REMOVED: Premature sequence linking block ---

        # --- 2. Create EventRecord ---
        event_record_id = f"Event_{equip_instance_id_base}_{record_id_str}"  # Unique ID

        event_props = {
            "occursAtPlant": plant,
            "occursOnLine": line,
            "involvesEquipment": equipment,
            "rampUpFlag": row_data.get("RAMPUP_FLAG"),
            # AE Model Time Components
            "reportedDurationMinutes": row_data.get("TOTAL_TIME"),
            "businessExternalTimeMinutes": row_data.get("BUSINESS_EXTERNAL_TIME"),
            "plantAvailableTimeMinutes": row_data.get("PLANT_AVAILABLE_TIME"),
            "effectiveRuntimeMinutes": row_data.get("EFFECTIVE_RUNTIME"),
            "plantDecisionTimeMinutes": row_data.get("PLANT_DECISION_TIME"),
            "productionAvailableTimeMinutes": row_data.get("PRODUCTION_AVAILABLE_TIME"),
            "downtimeMinutes": row_data.get(
                "DOWNTIME"
            ),  # Maps to UnplannedState total?
            "runTimeMinutes": row_data.get("RUN_TIME"),  # Maps to RuntimeState total?
            "notEnteredTimeMinutes": row_data.get(
                "NOT_ENTERED"
            ),  # Included in Unplanned?
            "waitingTimeMinutes": row_data.get(
                "WAITING_TIME"
            ),  # Maps to WaitingState total?
            "plantExperimentationTimeMinutes": row_data.get("PLANT_EXPERIMENTATION"),
            "allMaintenanceTimeMinutes": row_data.get("ALL_MAINTENANCE"),
            "autonomousMaintenanceTimeMinutes": row_data.get("AUTONOMOUS_MAINTENANCE"),
            "plannedMaintenanceTimeMinutes": row_data.get("PLANNED_MAINTENANCE"),
            "changeoverDurationMinutes": row_data.get("CHANGEOVER_DURATION"),
            "cleaningSanitizationTimeMinutes": row_data.get(
                "CLEANING_AND_SANITIZATION"
            ),
            "lunchBreakTimeMinutes": row_data.get("LUNCH_AND_BREAK"),
            "meetingTrainingTimeMinutes": row_data.get("MEETING_AND_TRAINING"),
            "noDemandTimeMinutes": row_data.get("NO_DEMAND"),
            # Production Quantities
            "goodProductionQty": row_data.get("GOOD_PRODUCTION_QTY"),
            "rejectProductionQty": row_data.get("REJECT_PRODUCTION_QTY"),
            # Raw Descriptions (NEW)
            "rawStateDescription": clean_string_value(
                row_data.get("UTIL_STATE_DESCRIPTION")
            ),
            "rawReasonDescription": clean_string_value(
                row_data.get("UTIL_REASON_DESCRIPTION")
            ),
        }
        event_record = get_or_create_instance(
            onto.EventRecord, event_record_id, event_props
        )

        # --- 3. Add TimeInterval ---
        start_time = parse_datetime_with_tz(row_data.get("JOB_START_TIME_LOC"))
        end_time = parse_datetime_with_tz(row_data.get("JOB_END_TIME_LOC"))

        if start_time and end_time:
            interval_id = f"Interval_{event_record_id}"
            interval = get_or_create_instance(
                onto.TimeInterval,
                interval_id,
                {"startTime": start_time, "endTime": end_time},
            )
            event_record.occursDuring = interval  # Functional

            try:
                duration_seconds = (end_time - start_time).total_seconds()
                if duration_seconds >= 0:
                    event_record.calculatedDurationSeconds = (
                        duration_seconds  # Functional
                    )
                else:
                    logger.warning(
                        f"Row {record_id_str}: Negative duration calculated ({duration_seconds}s). End time may be before start time."
                    )
            except Exception as dur_err:
                logger.warning(
                    f"Row {record_id_str}: Could not calculate duration: {dur_err}"
                )
        else:
            logger.warning(
                f"Row {record_id_str}: Missing or invalid JOB_START/END_TIME_LOC. Cannot create TimeInterval or calculate duration."
            )

        # --- 4. Add Utilization State (based on AE_MODEL_CATEGORY) ---
        ae_category_raw = row_data.get("AE_MODEL_CATEGORY")
        state_instance = None
        TargetStateClass = None

        if ae_category_raw:
            ae_category_clean = str(ae_category_raw).strip().lower()
            TargetStateClass = AE_CATEGORY_CLASS_MAP.get(ae_category_clean)

            if TargetStateClass:
                # Get the shared instance for this AE state (e.g., UnplannedState_Unplanned)
                state_instance = get_ae_state_instance(
                    ae_category_raw, TargetStateClass
                )  # Use original name for helper ID
            else:
                logger.warning(
                    f"Row {record_id_str}: Unknown AE_MODEL_CATEGORY '{ae_category_raw}'. Mapping to UnknownAEState."
                )
                TargetStateClass = onto.UnknownAEState
                state_instance = get_ae_state_instance(
                    "Unknown", TargetStateClass
                )  # Shared Unknown instance
        else:
            logger.warning(
                f"Row {record_id_str}: Missing AE_MODEL_CATEGORY. Mapping to UnknownAEState."
            )
            TargetStateClass = onto.UnknownAEState
            state_instance = get_ae_state_instance(
                "Unknown", TargetStateClass
            )  # Shared Unknown instance

        if state_instance:
            event_record.hasState = state_instance  # Functional

        # --- REMOVED: Reason mapping logic ---
        # Raw reason text is now captured directly in event_props using rawReasonDescription

        # --- 5. Add Process Context (Material, Order, Shift, Crew) ---
        material_id = row_data.get("MATERIAL_ID")
        if material_id:
            material = get_or_create_instance(
                onto.Material,
                f"Material_{material_id}",
                {
                    "materialId": material_id,
                    "materialDescription": row_data.get(
                        "SHORT_MATERIAL_ID"
                    ),  # Or MATERIAL_DESC
                    "materialUOM": row_data.get("MATERIAL_UOM"),
                },
            )
            event_record.processesMaterial = [material]  # Non-functional append unique

        order_id_raw = row_data.get("PRODUCTION_ORDER_ID")
        if order_id_raw:
            order_id = (
                str(int(order_id_raw))
                if isinstance(order_id_raw, float) and order_id_raw.is_integer()
                else str(order_id_raw)
            )
            order = get_or_create_instance(
                onto.ProductionOrder,
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
                onto.Shift, f"Shift_{shift_name}", {"shiftName": shift_name}
            )
            event_record.duringShift = shift  # Functional

        crew_id = row_data.get("CREW_ID")
        if crew_id:
            crew = get_or_create_instance(
                onto.Crew, f"Crew_{crew_id}", {"crewId": crew_id}
            )
            event_record.operatedByCrew = crew  # Functional

        # logger.debug(f"--- Successfully mapped row {record_id_str} ---")

    except Exception as e:
        logger.error(
            f"Error mapping row {record_id_str} to ontology: {e}", exc_info=True
        )
        raise  # Re-raise to potentially stop execution or be caught higher up


# =============================================================================
# Query Functions (Examples - REVISED for new states/properties)
# =============================================================================


def find_equipment_by_type(equipment_type: str) -> List[Equipment]:
    """Find equipment instances by their base type."""
    # No change needed here
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
    # --- ADD DEBUGGING ---
    downstream_prop_value = getattr(equipment, "isImmediatelyUpstreamOf", None)
    logger.debug(
        f"Querying downstream for {equipment.name}: Found isImmediatelyUpstreamOf = {downstream_prop_value}"
    )
    # --- END DEBUGGING ---
    downstream = list(downstream_prop_value) if downstream_prop_value else []
    logger.debug(
        f"Returning {len(downstream)} downstream equipment for {equipment.name}"
    )
    return downstream


def find_upstream_equipment(equipment: Equipment) -> List[Equipment]:
    """Find equipment immediately upstream of the given equipment."""
    if not equipment:
        return []
    # --- ADD DEBUGGING ---
    upstream_prop_value = getattr(equipment, "isImmediatelyDownstreamOf", None)
    logger.debug(
        f"Querying upstream for {equipment.name}: Found isImmediatelyDownstreamOf = {upstream_prop_value}"
    )
    # --- END DEBUGGING ---
    upstream = list(upstream_prop_value) if upstream_prop_value else []
    logger.debug(f"Returning {len(upstream)} upstream equipment for {equipment.name}")
    return upstream


# Example query adjusted for new structure
def find_longest_unplanned_events(
    equipment: Equipment, count: int = 1
) -> List[Dict[str, Any]]:
    """Find the longest event(s) for a piece of equipment classified as UnplannedState."""
    results = []
    if not equipment or not isinstance(equipment, onto.Equipment):
        logger.warning("Invalid equipment provided.")
        return results

    logger.info(f"Searching for longest UnplannedState events for {equipment.name}...")

    # Get the shared instance for UnplannedState
    try:
        # Assumes AE category name is 'Unplanned'
        unplanned_state_instance = get_ae_state_instance(
            "Unplanned", onto.UnplannedState
        )
    except Exception as e:
        logger.error(f"Could not get UnplannedState instance: {e}")
        return results  # Cannot proceed without the state instance

    # Search for events involving the equipment and having the UnplannedState
    unplanned_events = list(
        onto.search(
            type=onto.EventRecord,
            involvesEquipment=equipment,
            hasState=unplanned_state_instance,
        )
    )

    if not unplanned_events:
        logger.info(f"No UnplannedState events found for {equipment.name}.")
        return results

    # Sort by calculated duration (or reported duration as fallback)
    def get_duration(event):
        if (
            hasattr(event, "calculatedDurationSeconds")
            and event.calculatedDurationSeconds is not None
        ):
            return event.calculatedDurationSeconds
        elif (
            hasattr(event, "reportedDurationMinutes")
            and event.reportedDurationMinutes is not None
        ):
            # Convert fallback to seconds for consistent sorting
            return event.reportedDurationMinutes * 60
        return 0  # Treat events with no duration as shortest

    unplanned_events.sort(key=get_duration, reverse=True)

    # Get top N events and their reasons
    top_events = unplanned_events[:count]
    for event in top_events:
        results.append(
            {
                "event_iri": event.iri,
                "duration_seconds": get_duration(event),
                "raw_state_desc": getattr(event, "rawStateDescription", "N/A"),
                "raw_reason_desc": getattr(event, "rawReasonDescription", "N/A"),
                "start_time": (
                    getattr(event.occursDuring, "startTime", None)
                    if event.occursDuring
                    else None
                ),
                "end_time": (
                    getattr(event.occursDuring, "endTime", None)
                    if event.occursDuring
                    else None
                ),
            }
        )

    logger.info(
        f"Found {len(results)} longest UnplannedState event(s) for {equipment.name}."
    )
    return results


# =============================================================================
# Post-Processing: Link Equipment by Sequence (Unchanged)
# =============================================================================


def link_equipment_by_sequence(ontology: owl.Ontology):
    """
    Iterates through all lines and links equipment instances based on their
    sequenceOrder property (n is upstream of n+1). Relies on Owlready2 for inverse.
    """
    logger.info("Starting post-processing step: Linking equipment by sequence order...")
    link_count = 0
    processed_lines = 0

    all_lines = list(ontology.search(type=onto.Line))
    logger.info(f"Found {len(all_lines)} lines to process for equipment sequencing.")

    for line in all_lines:
        processed_lines += 1
        logger.debug(f"--- Processing line: {line.name} ---")

        equipment_on_line_with_order = []
        equip_list = list(getattr(line, "hasEquipment", []))
        logger.debug(
            f"Line {line.name}: Found {len(equip_list)} equipment instances total."
        )

        # Collect equipment that has a valid sequenceOrder
        for equip in equip_list:
            seq_order_val = getattr(equip, "sequenceOrder", None)
            if seq_order_val is not None:
                try:
                    seq_order_int = int(seq_order_val)
                    equipment_on_line_with_order.append((seq_order_int, equip))
                    logger.debug(
                        f"  Equipment {equip.name} (Type: {getattr(equip,'equipmentBaseType','N/A')}) has sequenceOrder: {seq_order_int}"
                    )
                except (ValueError, TypeError):
                    logger.warning(
                        f"  Equipment {equip.name} on line {line.name} has non-integer sequenceOrder '{seq_order_val}'. Skipping for linking."
                    )

        if len(equipment_on_line_with_order) < 2:
            logger.debug(
                f"Line {line.name}: Found only {len(equipment_on_line_with_order)} equipment with sequenceOrder. Need at least 2 to link. Skipping line."
            )
            continue

        # Sort equipment by sequenceOrder
        sorted_equipment_pairs = sorted(
            equipment_on_line_with_order, key=lambda item: item[0]
        )
        sorted_equipment = [pair[1] for pair in sorted_equipment_pairs]
        sorted_orders = [pair[0] for pair in sorted_equipment_pairs]
        logger.debug(
            f"Line {line.name}: Sorted equipment with order: {[f'{e.name}({o})' for e, o in zip(sorted_equipment, sorted_orders)]}"
        )

        # Link adjacent sequences (n to n+1)
        line_links_made = 0
        for i in range(len(sorted_equipment) - 1):
            upstream_eq = sorted_equipment[i]
            downstream_eq = sorted_equipment[i + 1]
            upstream_order = sorted_orders[i]
            downstream_order = sorted_orders[i+1]

            logger.debug(f"  Checking pair: {upstream_eq.name}({upstream_order}) -> {downstream_eq.name}({downstream_order})")

            # Check if sequence order is consecutive
            if downstream_order == upstream_order + 1:
                logger.debug(f"    Orders are consecutive. Attempting to link.")
                pair_linked = False

                # --- ONLY UPDATE ONE SIDE using simple assignment ---
                current_downstream = list(getattr(upstream_eq, "isImmediatelyUpstreamOf", []))
                if downstream_eq not in current_downstream:
                    current_downstream.append(downstream_eq)
                    # Assign the updated list back
                    upstream_eq.isImmediatelyUpstreamOf = current_downstream
                    logger.info(f"    LINKED: {upstream_eq.name} --isImmediatelyUpstreamOf--> {downstream_eq.name} (Owlready2 should handle inverse)")
                    pair_linked = True
                else:
                    logger.debug(f"    Link {upstream_eq.name} -> {downstream_eq.name} already exists.")

                if pair_linked:
                    link_count += 1
                    line_links_made += 1
                    logger.debug(
                        f"    Link {upstream_eq.name} -> {downstream_eq.name} already exists."
                    )

                # --- REMOVED Manual update of isImmediatelyDownstreamOf ---

                if pair_linked:
                    link_count += 1
                    line_links_made += 1

            elif downstream_order > upstream_order + 1:
                logger.debug(
                    f"    Gap in sequence order detected between {upstream_eq.name} ({upstream_order}) and {downstream_eq.name} ({downstream_order}). No direct link created."
                )
            elif downstream_order <= upstream_order:
                logger.warning(
                    f"    Non-increasing or duplicate sequence order detected between {upstream_eq.name} ({upstream_order}) and {downstream_eq.name} ({downstream_order}). Check configuration/data. No link created."
                )

        logger.debug(
            f"--- Finished processing line: {line.name}. Links created on this line: {line_links_made} ---"
        )

    logger.info(
        f"Finished linking equipment by sequence. Created/verified approximately {link_count} link pairs."
    )


# =============================================================================
# Main Execution Block (Adjusted for New Ontology/File Names)
# =============================================================================


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Manufacturing Ontology Builder")
    parser.add_argument("--input", "-i", required=True, help="Input CSV file path")
    settings = get_ontology_settings()
    default_output = settings.get("default_output_file")  # Get updated default
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
    args = parse_arguments()
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))

    input_path = Path(args.input)
    if not input_path.is_file():  # More specific check
        logger.critical(f"Input file not found or is not a file: {input_path}")
        return 1

    try:
        # Load and preprocess
        df_raw = load_csv_data(args.input)
        processed_df = preprocess_manufacturing_data(df_raw)

        # Check if preprocessing resulted in empty dataframe
        if processed_df.empty:
            logger.critical(
                "Preprocessing resulted in an empty DataFrame. Cannot proceed."
            )
            return 1

        # Check again for AE_MODEL_CATEGORY after preprocessing
        if (
            "AE_MODEL_CATEGORY" not in processed_df.columns
            or processed_df["AE_MODEL_CATEGORY"].isnull().all()
        ):
            logger.critical(
                "CRITICAL: AE_MODEL_CATEGORY column is missing or entirely null after preprocessing. State mapping will fail."
            )
            return 1  # Stop execution

        # Get configuration
        equipment_type_seq = get_equipment_type_sequence_order()
        equipment_seq_overrides = get_equipment_sequence_overrides()

        # Use ontology context for mapping AND linking operations
        logger.info("Entering main ontology context for population and linking...")
        with onto:
            # --- Ontology Population ---
            stats = {"total_rows": len(processed_df), "processed_rows": 0, "error_rows": 0}
            logger.info(f"Populating ontology from {stats['total_rows']} processed rows...")
            row_count = len(processed_df)
            data_rows = processed_df.to_dict("records")

            for i, row_data in enumerate(data_rows):
                try:
                    map_row_to_ontology(
                        row_data, equipment_seq_overrides, equipment_type_seq
                    )
                    stats["processed_rows"] += 1
                except Exception as map_err:
                    stats["error_rows"] += 1
                # Log progress
                if (i + 1) % 5000 == 0 or (i + 1) == row_count:
                    logger.info(
                        f"Mapped {i + 1}/{row_count} rows ({(i + 1) / row_count:.1%})"
                    )

            logger.info(f"Mapped {stats['processed_rows']} rows successfully.")

            # Check for errors before proceeding with linking
            if stats["error_rows"] > 0:
                logger.warning(f"{stats['error_rows']} errors occurred during row mapping. Ontology may be incomplete.")

            # Post-process: Link equipment by sequence order (NOW INSIDE with onto)
            logger.info("Running post-processing: Linking equipment sequences...")
            # Ensure link_equipment_by_sequence uses the version that modifies only one side
            link_equipment_by_sequence(onto)

        logger.info("Exited main ontology context.")

        # Save ontology
        output_path = args.output
        output_format = settings.get("format", "rdfxml")
        logger.info(f"Saving ontology to {output_path} in format {output_format}")
        try:
            onto.save(file=output_path, format=output_format)
            logger.info("Ontology saved successfully.")
        except Exception as save_err:
            logger.critical(f"Failed to save ontology: {save_err}", exc_info=True)
            return 1

        # Run example queries
        logger.info("--- Running Example Queries ---")
        example_equip_type = "CasePacker"
        case_packers = find_equipment_by_type(example_equip_type)
        logger.info(
            f"Found {len(case_packers)} {example_equip_type} equipment instances."
        )

        if case_packers:
            # Find one associated with a line for more interesting queries
            cp1 = None
            for cp in case_packers:
                if getattr(cp, "isPartOfLine", None):
                    cp1 = cp
                    break

            if cp1:
                logger.info(f"Querying around example {example_equip_type}: {cp1.name}")
                upstream = find_upstream_equipment(cp1)
                downstream = find_downstream_equipment(cp1)
                logger.info(f"  Upstream: {[e.name for e in upstream]}")
                logger.info(f"  Downstream: {[e.name for e in downstream]}")

                # Example: Find longest unplanned event for this CasePacker
                longest_unplanned = find_longest_unplanned_events(cp1, count=1)
                if longest_unplanned:
                    event_info = longest_unplanned[0]
                    logger.info(
                        f"  Longest Unplanned Event (~{event_info['duration_seconds']:.0f}s):"
                    )
                    logger.info(f"    State Desc (raw): {event_info['raw_state_desc']}")
                    logger.info(
                        f"    Reason Desc (raw): {event_info['raw_reason_desc']}"
                    )
                else:
                    logger.info(f"  No UnplannedState events found for {cp1.name}.")
            else:
                logger.info(
                    f"Could not find a {example_equip_type} associated with a line for detailed queries."
                )

        # --- Final Statistics ---
        logger.info("--- Processing Summary ---")
        logger.info(f"Input rows processed: {stats['total_rows']}")
        # logger.info(f"Rows successfully mapped: {stats['processed_rows']}") # Less useful if errors are counted
        if stats["error_rows"] > 0:
            logger.warning(f"Rows with errors during mapping: {stats['error_rows']}")
        else:
            logger.info("No errors detected during row mapping.")
        logger.info("---------------------------")

        logger.info("Processing completed.")
        return 0

    except Exception as e:
        logger.critical(
            f"A critical error occurred in the main process: {e}", exc_info=True
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
