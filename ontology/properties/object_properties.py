"""Object property (relationship) definitions for the manufacturing ontology."""

import owlready2 as owl
from ontology.core import onto
from ontology.classes.assets import Equipment, Line, Plant
from ontology.classes.events import EventRecord
from ontology.classes.location import PhysicalArea
from ontology.classes.organizational import FocusFactory
from ontology.classes.process import Material, ProductionOrder, Crew
from ontology.classes.time_related import TimeInterval, Shift
from ontology.classes.utilization import UtilizationState, UtilizationReason
from ontology.classes.location import Country, StrategicLocation

# Must use with onto: to ensure all definitions are within the ontology scope
with onto:
    # --- Linking EventRecord ---
    class occursAtPlant(owl.ObjectProperty):
        """Relates an event record to the plant where it occurred."""

        domain = [EventRecord]
        range = [Plant]

    class occursOnLine(owl.ObjectProperty):
        """Relates an event record to the line where it occurred."""

        domain = [EventRecord]
        range = [Line]

    class involvesEquipment(owl.ObjectProperty):
        """Relates an event record to the equipment involved."""

        domain = [EventRecord]
        range = [Equipment]

    class hasState(owl.ObjectProperty):
        """Relates an event record to its utilization state."""

        domain = [EventRecord]
        range = [UtilizationState]

    class hasReason(owl.ObjectProperty):
        """Relates an event record to its utilization reason."""

        domain = [EventRecord]
        range = [UtilizationReason]

    class occursDuring(owl.ObjectProperty):
        """Relates an event record to its time interval."""

        domain = [EventRecord]
        range = [TimeInterval]
        functional = True

    class processesMaterial(owl.ObjectProperty):
        """Relates an event record to the material being processed."""

        domain = [EventRecord]
        range = [Material]

    class relatesToOrder(owl.ObjectProperty):
        """Relates an event record to the production order."""

        domain = [EventRecord]
        range = [ProductionOrder]

    class duringShift(owl.ObjectProperty):
        """Relates an event record to the shift during which it occurred."""

        domain = [EventRecord]
        range = [Shift]

    class operatedByCrew(owl.ObjectProperty):
        """Relates an event record to the crew operating the equipment."""

        domain = [EventRecord]
        range = [Crew]  # Or link Crew to Shift? Linking to Record is direct.

    # --- Asset / Location / Org Relationships ---
    class locatedInPlant(owl.ObjectProperty):
        """Relates an entity to the plant where it's located."""

        domain = [Line, Equipment, PhysicalArea, FocusFactory]
        range = [Plant]

    class isPartOfLine(owl.ObjectProperty):
        """Relates equipment to the line it belongs to."""

        domain = [Equipment]
        range = [Line]

    class hasLine(owl.ObjectProperty):
        """Relates a plant to a line it contains."""

        domain = [Plant, PhysicalArea]
        range = [Line]
        inverse_property = locatedInPlant

    class hasEquipment(owl.ObjectProperty):
        """Relates a line to equipment it contains."""

        domain = [Line]
        range = [Equipment]
        inverse_property = isPartOfLine

    class locatedInArea(owl.ObjectProperty):
        """Relates an entity to the physical area it's located in."""

        domain = [Line, Equipment]
        range = [PhysicalArea]

    class hasPhysicalArea(owl.ObjectProperty):
        """Relates a plant to a physical area it contains."""

        domain = [FocusFactory]
        range = [PhysicalArea]

    class partOfFocusFactory(owl.ObjectProperty):
        """Relates an entity to the focus factory it belongs to."""

        domain = [PhysicalArea, Line, Equipment]
        range = [FocusFactory]

    class hasFocusFactory(owl.ObjectProperty):
        """Relates a plant to focus factories it contains."""

        domain = [Plant]
        range = [FocusFactory]
        inverse_property = locatedInPlant

    class hasArea(owl.ObjectProperty):
        """Relates a focus factory to physical areas it contains."""

        domain = [FocusFactory]
        range = [PhysicalArea]
        inverse_property = partOfFocusFactory

    class locatedInCountry(owl.ObjectProperty):
        """Relates a plant to the country it's located in."""

        domain = [Plant]
        range = [Country]

    class hasStrategicLocation(owl.ObjectProperty):
        """Relates a plant to its strategic location classification."""

        domain = [Plant]
        range = [StrategicLocation]

    # --- Equipment Sequence Relationships ---
    class isImmediatelyUpstreamOf(owl.ObjectProperty):
        """Relates equipment to the equipment immediately downstream of it."""

        domain = [Equipment]
        range = [Equipment]

    class isImmediatelyDownstreamOf(owl.ObjectProperty):
        """Relates equipment to the equipment immediately upstream of it."""

        domain = [Equipment]
        range = [Equipment]
        inverse_property = isImmediatelyUpstreamOf


# Export properties for easy import
__all__ = [
    "occursAtPlant",
    "occursOnLine",
    "involvesEquipment",
    "hasState",
    "hasReason",
    "occursDuring",
    "processesMaterial",
    "relatesToOrder",
    "duringShift",
    "operatedByCrew",
    "locatedInPlant",
    "isPartOfLine",
    "hasLine",
    "hasEquipment",
    "locatedInArea",
    "hasPhysicalArea",
    "partOfFocusFactory",
    "hasFocusFactory",
    "hasArea",
    "locatedInCountry",
    "hasStrategicLocation",
    "isImmediatelyUpstreamOf",
    "isImmediatelyDownstreamOf",
]
