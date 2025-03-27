"""Properties for the manufacturing ontology."""

# Import all properties from submodules
from ontology.properties.object_properties import *
from ontology.properties.data_properties import *

# Add all property names to __all__
__all__ = [
    # Object Properties
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
    "locatedInCountry",
    "hasStrategicLocation",
    "isImmediatelyUpstreamOf",
    "isImmediatelyDownstreamOf",
    # Data Properties
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
