"""Helper functions for working with the manufacturing ontology."""

import owlready2 as owl
from typing import Dict, Any, Optional, List, Type, Union
from ontology.core import onto
import logging

logger = logging.getLogger(__name__)


def get_or_create_instance(
    cls: Type,
    name_or_id: str,
    properties: Optional[Dict[str, Any]] = None,
    namespace: owl.Namespace = onto,
) -> owl.Thing:
    """Get existing instance by name or create a new one.

    Args:
        cls: The owlready2 class to create an instance of
        name_or_id: Unique identifier for the instance
        properties: Dictionary of property names and values to set
        namespace: The ontology namespace to use

    Returns:
        The existing or newly created instance
    """
    # Sanitize the instance name for OWL
    instance_name = name_or_id.replace(" ", "_").replace("-", "_")

    # Check if instance already exists
    existing = namespace.search_one(iri=f"*{instance_name}")
    if existing is not None and isinstance(existing, cls):
        # Update properties if provided
        if properties:
            for prop_name, value in properties.items():
                if value is not None:
                    # Set property as a list for non-functional properties
                    if hasattr(existing, prop_name):
                        # If property already exists, check if it's a list
                        current_value = getattr(existing, prop_name)
                        if isinstance(current_value, list):
                            if value not in current_value:
                                # Ensure no None values in the list
                                if value is not None:
                                    current_value.append(value)
                        else:
                            setattr(existing, prop_name, [value])
                    else:
                        # New property, set as list
                        setattr(existing, prop_name, [value])
        return existing

    # Create new instance
    logger.debug(f"Creating new instance of {cls.__name__}: {instance_name}")
    new_instance = cls(instance_name, namespace=namespace)

    # Set properties if provided
    if properties:
        for prop_name, value in properties.items():
            if value is not None:
                # Always set properties as lists to handle non-functional properties
                setattr(new_instance, prop_name, [value])

    return new_instance


def find_equipment_by_type(equipment_type: str) -> List[owl.Thing]:
    """Find equipment instances by their base type.

    Args:
        equipment_type: The equipment type to search for (e.g., "CasePacker")

    Returns:
        List of equipment instances matching the type
    """
    return [
        e
        for e in onto.Equipment.instances()
        if hasattr(e, "equipmentBaseType")
        and e.equipmentBaseType
        and e.equipmentBaseType[0] == equipment_type
    ]
