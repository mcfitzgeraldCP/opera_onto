"""Data property (attribute) definitions for the manufacturing ontology."""

import owlready2 as owl
from ontology.core import onto
from datetime import datetime
from ontology.classes.assets import Equipment, Line, Plant
from ontology.classes.events import EventRecord
from ontology.classes.process import Material, ProductionOrder
from ontology.classes.time_related import TimeInterval
from ontology.classes.utilization import UtilizationState, UtilizationReason

# Must use with onto: to ensure all definitions are within the ontology scope
with onto:
    # --- Time-related Properties ---
    class startTime(owl.DataProperty):
        """Start time of a time interval."""

        domain = [TimeInterval]
        range = [datetime]

    class endTime(owl.DataProperty):
        """End time of a time interval."""

        domain = [TimeInterval]
        range = [datetime]

    # --- Equipment Properties ---
    class equipmentId(owl.DataProperty):
        """Unique identifier for equipment."""

        domain = [Equipment]
        range = [str]

    class equipmentName(owl.DataProperty):
        """Human-readable name for equipment."""

        domain = [Equipment]
        range = [str]

    class equipmentBaseType(owl.DataProperty):
        """Base type of equipment (e.g., Filler, Cartoner)."""

        domain = [Equipment]
        range = [str]

    class sequenceOrder(owl.DataProperty):
        """Sequence order of equipment in a line."""

        domain = [Equipment]
        range = [int]

    # --- Plant Properties ---
    class plantId(owl.DataProperty):
        """Unique identifier for a plant."""

        domain = [Plant]
        range = [str]

    class plantDescription(owl.DataProperty):
        """Human-readable description of a plant."""

        domain = [Plant]
        range = [str]

    class latitude(owl.DataProperty):
        """Geographic latitude of a plant."""

        domain = [Plant]
        range = [float]

    class longitude(owl.DataProperty):
        """Geographic longitude of a plant."""

        domain = [Plant]
        range = [float]

    # --- Line Properties ---
    class lineId(owl.DataProperty):
        """Unique identifier for a line."""

        domain = [Line]
        range = [str]

    class lineName(owl.DataProperty):
        """Human-readable name for a line."""

        domain = [Line]
        range = [str]

    # --- Material Properties ---
    class materialId(owl.DataProperty):
        """Unique identifier for a material."""

        domain = [Material]
        range = [str]

    class materialDescription(owl.DataProperty):
        """Human-readable description of a material."""

        domain = [Material]
        range = [str]

    # --- Order Properties ---
    class orderId(owl.DataProperty):
        """Unique identifier for a production order."""

        domain = [ProductionOrder]
        range = [str]

    class orderDescription(owl.DataProperty):
        """Human-readable description of a production order."""

        domain = [ProductionOrder]
        range = [str]

    # --- Utilization Properties ---
    class stateDuration(owl.DataProperty):
        """Duration of a utilization state in seconds."""

        domain = [EventRecord]
        range = [float]

    class stateDescription(owl.DataProperty):
        """Human-readable description of a utilization state."""

        domain = [UtilizationState]
        range = [str]

    class reasonDescription(owl.DataProperty):
        """Human-readable description of a utilization reason."""

        domain = [UtilizationReason]
        range = [str]


# Export properties for easy import
__all__ = [
    "startTime",
    "endTime",
    "equipmentId",
    "equipmentName",
    "equipmentBaseType",
    "plantId",
    "plantDescription",
    "lineId",
    "lineName",
    "sequenceOrder",
    "materialId",
    "materialDescription",
    "orderId",
    "orderDescription",
    "stateDuration",
    "stateDescription",
    "reasonDescription",
    "latitude",
    "longitude",
]
