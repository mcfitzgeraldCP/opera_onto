"""Equipment-related query functions for the manufacturing ontology."""

import owlready2 as owl
from typing import List, Optional
import logging
from ontology.core import onto
from ontology.classes.assets import Equipment

logger = logging.getLogger(__name__)


def find_equipment_by_type(equipment_type: str) -> List[Equipment]:
    """Find equipment instances by their base type.

    Args:
        equipment_type: The equipment type to search for (e.g., "CasePacker")

    Returns:
        List of equipment instances matching the type
    """
    if not equipment_type:
        logger.warning("Cannot search for equipment with None/empty type")
        return []

    # Special handling for line-level items if needed
    is_line_level = equipment_type == "Line"

    matching_equipment = [
        e
        for e in onto.Equipment.instances()
        if hasattr(e, "equipmentBaseType")
        and e.equipmentBaseType
        and any(t for t in e.equipmentBaseType if t == equipment_type)
    ]
    logger.debug(f"Found {len(matching_equipment)} instances of {equipment_type}")
    return matching_equipment


def find_downstream_equipment(equipment: Equipment) -> List[Equipment]:
    """Find equipment immediately downstream of the given equipment.

    Args:
        equipment: The equipment to find downstream equipment for

    Returns:
        List of equipment instances immediately downstream of the given equipment
    """
    if not hasattr(equipment, "isImmediatelyUpstreamOf"):
        logger.debug(f"Equipment {equipment.name} has no downstream equipment")
        return []

    downstream = list(equipment.isImmediatelyUpstreamOf)
    logger.debug(f"Found {len(downstream)} downstream equipment for {equipment.name}")
    return downstream


def find_upstream_equipment(equipment: Equipment) -> List[Equipment]:
    """Find equipment immediately upstream of the given equipment.

    Args:
        equipment: The equipment to find upstream equipment for

    Returns:
        List of equipment instances immediately upstream of the given equipment
    """
    if not hasattr(equipment, "isImmediatelyDownstreamOf"):
        logger.debug(f"Equipment {equipment.name} has no upstream equipment")
        return []

    upstream = list(equipment.isImmediatelyDownstreamOf)
    logger.debug(f"Found {len(upstream)} upstream equipment for {equipment.name}")
    return upstream


def find_equipment_by_id(equipment_id: str) -> Optional[Equipment]:
    """Find equipment by its ID.

    Args:
        equipment_id: The equipment ID to search for

    Returns:
        Equipment instance with the given ID, or None if not found
    """
    for e in onto.Equipment.instances():
        if (
            hasattr(e, "equipmentId")
            and e.equipmentId
            and e.equipmentId[0] == equipment_id
        ):
            return e
    logger.debug(f"No equipment found with ID: {equipment_id}")
    return None
