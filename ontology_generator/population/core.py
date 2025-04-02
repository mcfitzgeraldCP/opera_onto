"""
Core population module for the ontology generator.

This module provides the base functionality for ontology population, including the
PopulationContext class and property application functions.
"""
from typing import Dict, Any, Optional, List, Set, Tuple, Union, Callable
import logging
import pandas as pd

from owlready2 import (
    Ontology, Thing, ThingClass, PropertyClass,
    locstr, FunctionalProperty, ObjectProperty, DataProperty, ObjectPropertyClass, DataPropertyClass
)

from ontology_generator.utils.logging import pop_logger
from ontology_generator.config import XSD_TYPE_MAP
from ontology_generator.utils.types import safe_cast, sanitize_name

# Type Alias for registry used in linking
IndividualRegistry = Dict[Tuple[str, str], Thing] # Key: (entity_type_str, unique_id_str), Value: Individual Object

class PopulationContext:
    """
    Holds references to ontology elements needed during population.
    
    Attributes:
        onto: The ontology being populated
        classes: Dictionary of defined classes
        props: Dictionary of defined properties
        is_functional: Dictionary indicating whether properties are functional
    """
    def __init__(self, 
                 onto: Ontology, 
                 defined_classes: Dict[str, ThingClass], 
                 defined_properties: Dict[str, PropertyClass], 
                 property_is_functional: Dict[str, bool]):
        """
        Initialize the population context.
        
        Args:
            onto: The ontology being populated
            defined_classes: Dictionary mapping class names to class objects
            defined_properties: Dictionary mapping property names to property objects
            property_is_functional: Dictionary mapping property names to boolean functionality flags
        """
        self.onto = onto
        self.defined_classes = defined_classes
        self.defined_properties = defined_properties
        self.property_is_functional = property_is_functional
        self._property_cache = {} # Cache for faster property lookup
        self._class_cache = {} # Cache for faster class lookup

    def get_class(self, name: str) -> Optional[ThingClass]:
        """
        Get a class by name.
        
        Args:
            name: The name of the class
            
        Returns:
            The class object or None if not found
        """
        if name in self._class_cache:
            return self._class_cache[name]

        cls = self.defined_classes.get(name)
        if not cls: 
            pop_logger.error(f"Essential class '{name}' not found in defined_classes.")
            return None
        # Basic validation (could add more specific checks if needed)
        if not isinstance(cls, ThingClass):
             pop_logger.error(f"Item '{name}' found but is not a ThingClass (checked via isinstance).")
             return None

        self._class_cache[name] = cls
        return cls

    def get_prop(self, name: str) -> Optional[PropertyClass]:
        """
        Get a property by name.
        
        Args:
            name: The name of the property
            
        Returns:
            The property object or None if not found
        """
        if name in self._property_cache:
            return self._property_cache[name]

        prop = self.defined_properties.get(name)
        if not prop:
            pop_logger.warning(f"Property '{name}' not found in defined properties.")
            return None
        # Basic validation (could add more specific checks if needed)
        if not isinstance(prop, (ObjectPropertyClass, DataPropertyClass)):
            pop_logger.error(f"Item '{name}' found but is not a PropertyClass (Object or Data).")
            return None

        self._property_cache[name] = prop
        return prop

    def set_prop(self, individual: Thing, prop_name: str, value: Any) -> None:
        """
        Safely sets a property value using the context.
        
        Args:
            individual: The individual to set the property on
            prop_name: The name of the property to set
            value: The value to set
        """
        prop = self.get_prop(prop_name)
        if not prop:
            # Error logged by get_prop
            return
        is_functional = self.property_is_functional.get(prop_name, False) # Assume non-functional if not specified

        try:
            _set_property_value(individual, prop, value, is_functional)
        except Exception as e:
            pop_logger.error(f"Error setting property '{prop_name}' on individual '{individual.name}' with value '{value}': {e}", exc_info=True)


def _set_property_value(individual: Thing, prop: PropertyClass, value: Any, is_functional: bool) -> None:
    """
    Helper to set functional or non-functional properties, checking existence first.
    
    Args:
        individual: The individual to set the property on
        prop: The property to set
        value: The value to set
        is_functional: Whether the property is functional
    """
    if value is None: 
        return  # Don't set None values

    prop_name = prop.python_name  # Use Python name for attribute access

    try:
        if is_functional:
            # Functional: Use setattr, potentially overwriting. Check if different first.
            current_value = getattr(individual, prop_name, None)
            # Handle comparison carefully, especially for complex types like lists/individuals
            # Simple direct comparison works for primitives and owlready individuals/locstr
            if current_value != value:
                setattr(individual, prop_name, value)
                pop_logger.debug(f"Set functional property {individual.name}.{prop.name} = {repr(value)}")
        else:
            # Non-Functional: Use append, check if value already exists.
            current_values = getattr(individual, prop_name, [])
            if not isinstance(current_values, list):  # Ensure it's a list for append
                current_values = [current_values] if current_values is not None else []

            if value not in current_values:
                # owlready handles adding to the list via direct attribute access
                getattr(individual, prop_name).append(value)
                pop_logger.debug(f"Appended non-functional property {individual.name}.{prop.name} = {repr(value)}")

    except Exception as e:
        pop_logger.error(f"Error setting property '{prop.name}' on individual '{individual.name}' with value '{repr(value)}': {e}", exc_info=False)


def set_prop_if_col_exists(
    context: PopulationContext,
    individual: Thing,
    prop_name: str,
    col_name: str,
    row: Dict[str, Any],
    cast_func: Callable,
    target_type: type,
    logger
) -> bool:
    """Helper function to check if column exists, cast value, and set property if value exists."""
    # Check if column exists in the row
    if col_name not in row:
        logger.error(f"Missing required column '{col_name}' for property '{prop_name}' on individual '{individual.name}' in row: {truncate_row_repr(row)}")
        return False

    # Column exists but might be empty/None/NaN
    raw_value = row.get(col_name)
    if pd.isna(raw_value) or raw_value == '' or raw_value is None:
        logger.debug(f"Column '{col_name}' exists but has null/empty value for property '{prop_name}' on individual '{individual.name}'")
        return False

    # Cast value to target type
    value = cast_func(raw_value, target_type)
    if value is None:  # Cast failed
        logger.warning(f"Failed to cast value '{raw_value}' from column '{col_name}' to type {target_type.__name__} for property '{prop_name}' on individual '{individual.name}'")
        return False

    # Set the property
    context.set_prop(individual, prop_name, value)
    return True

def truncate_row_repr(row: Dict[str, Any], max_length: int = 100) -> str:
    """Create a truncated string representation of a row for logging."""
    row_str = str(row)
    if len(row_str) > max_length:
        return row_str[:max_length] + "..."
    return row_str


def get_or_create_individual(
    onto_class: ThingClass,
    individual_name_base: Any,
    onto: Ontology,
    registry: IndividualRegistry, # Use the defined type alias
    add_labels: Optional[List[str]] = None
) -> Optional[Thing]:
    """
    Gets an individual from the registry or creates a new one if it doesn't exist.
    Uses a combination of class name and a base ID/name for the registry key.
    Adds labels if provided.

    Args:
        onto_class: The owlready2 class of the individual.
        individual_name_base: The base name or ID (will be sanitized) used for the individual's name and registry key.
        onto: The ontology instance.
        registry: The dictionary acting as the central registry.
        add_labels: Optional list of labels to add to the individual (if created or found).

    Returns:
        The existing or newly created individual, or None if creation fails.
    """
    if not onto_class or not individual_name_base:
        pop_logger.error(f"Missing onto_class ({onto_class}) or individual_name_base ({individual_name_base}) for get_or_create.")
        return None

    # Sanitize the base name for use in IRI and registry key
    sanitized_name_base = sanitize_name(str(individual_name_base))
    if not sanitized_name_base:
        pop_logger.error(f"Could not sanitize base name '{individual_name_base}' for individual of class '{onto_class.name}'.")
        return None

    class_name_str = onto_class.name
    registry_key = (class_name_str, sanitized_name_base)

    # Check registry first
    if registry_key in registry:
        existing_individual = registry[registry_key]
        pop_logger.debug(f"Found existing individual '{existing_individual.name}' (Key: {registry_key}) in registry.")
        # Optionally add labels even if found? Decide based on requirements.
        # if add_labels:
        #     for label in add_labels:
        #         if label and label not in existing_individual.label:
        #             existing_individual.label.append(label)
        return existing_individual

    # --- If not found, create ---
    individual_name = f"{class_name_str}_{sanitized_name_base}"

    try:
        with onto: # Ensure operation within ontology context
             # Check if an individual with this *exact* name already exists in owlready's cache
             # This can happen if safe_name produces the same result for different inputs,
             # or if an individual was created outside the registry mechanism.
            existing_by_name = onto.search_one(iri=f"*{individual_name}")
            if existing_by_name and isinstance(existing_by_name, onto_class):
                pop_logger.warning(f"Individual with name '{individual_name}' already exists in ontology but not registry (Key: {registry_key}). Returning existing one and adding to registry.")
                new_individual = existing_by_name
            elif existing_by_name:
                 # Name collision with an individual of a DIFFERENT class - should be rare with prefixing
                 pop_logger.error(f"Cannot create individual '{individual_name}': Name collision with existing individual '{existing_by_name.name}' of different class ({type(existing_by_name).__name__})")
                 return None
            else:
                # Create the new individual
                new_individual = onto_class(individual_name)
                pop_logger.info(f"Created new individual '{individual_name}' (Class: {class_name_str}, Base: '{individual_name_base}')")

                # Add labels if provided
                if add_labels:
                    for label in add_labels:
                        if label: # Ensure label is not empty
                            new_individual.label.append(str(label)) # Ensure labels are strings

        # Add to registry *after* successful creation
        registry[registry_key] = new_individual
        return new_individual

    except Exception as e:
        pop_logger.error(f"Failed to create individual '{individual_name}' of class '{class_name_str}': {e}", exc_info=True)
        return None


# --- Mappings Application Functions ---

def apply_data_property_mappings(
    individual: Thing,
    mappings: Dict[str, Dict[str, Any]],
    row: Dict[str, Any],
    context: PopulationContext,
    entity_name: str, # Name of the entity type being processed (for logging)
    logger # Pass logger explicitly
) -> None:
    """Applies data property mappings defined in the configuration."""
    if not mappings or 'data_properties' not in mappings:
        return

    data_prop_mappings = mappings.get('data_properties', {})

    for prop_name, details in data_prop_mappings.items():
        col_name = details.get('column')
        # Get cast type from mapping, default to string
        data_type_str = details.get('data_type', 'xsd:string')
        target_type = XSD_TYPE_MAP.get(data_type_str, str) # Map XSD type to Python type
        cast_func = safe_cast # Use the safe_cast utility

        if not col_name:
            logger.warning(f"Data property mapping for {entity_name}.{prop_name} is missing 'column'. Skipping.")
            continue

        # Use helper function to handle casting, existence check, and setting
        set_prop_if_col_exists(
            context=context,
            individual=individual,
            prop_name=prop_name,
            col_name=col_name,
            row=row,
            cast_func=cast_func,
            target_type=target_type,
            logger=logger
        )

def apply_object_property_mappings(
    individual: Thing,
    mappings: Dict[str, Dict[str, Any]],
    row: Dict[str, Any],
    context: PopulationContext,
    entity_name: str, # Name of the entity type being processed (for logging)
    logger, # Pass logger explicitly
    linking_context: IndividualRegistry, # The GLOBAL registry of ALL individuals
    individuals_in_row: Dict[str, Thing] # Individuals created/found specifically for THIS row in Pass 1
) -> None:
    """Applies ONLY object property mappings, using linking_context or individuals_in_row to find targets."""
    if not mappings or 'object_properties' not in mappings:
        return

    obj_prop_mappings = mappings.get('object_properties', {})
    links_applied_count = 0
    
    # Track missing entities per row to log only once
    missing_context_entities = set()

    for prop_name, details in obj_prop_mappings.items():
        target_class_name = details.get('target_class')
        col_name = details.get('column') # For linking via ID lookup in GLOBAL registry
        link_context_key = details.get('target_link_context') # For linking via key lookup in CURRENT row context

        if not target_class_name:
            logger.warning(f"Object property mapping for {entity_name}.{prop_name} is missing 'target_class'. Skipping link.")
            continue

        prop = context.get_prop(prop_name)
        if not prop or not isinstance(prop, ObjectPropertyClass): # Ensure it's an ObjectProperty
            logger.warning(f"Object property '{prop_name}' not found or not an ObjectProperty. Skipping link for {entity_name} {individual.name}.")
            continue

        # Add debug for EventRecord.involvesResource specifically
        if entity_name == "EventRecord" and prop_name == "involvesResource":
            if hasattr(individual, "involvesResource") and individual.involvesResource:
                logger.debug(f"EventRecord {individual.name} already has involvesResource set to {individual.involvesResource.name if hasattr(individual.involvesResource, 'name') else individual.involvesResource}")
                # Skip this property if already set
                continue

        # Find the target individual
        target_individual: Optional[Thing] = None
        lookup_method = "None"

        if col_name:
            # --- Link via Column Lookup (using GLOBAL registry) ---
            target_base_id = safe_cast(row.get(col_name), str)
            lookup_method = f"Column '{col_name}' (Registry Lookup)"
            if not target_base_id:
                logger.debug(f"Row {row.get('row_num', 'N/A')} - No target ID found in column '{col_name}' for link {entity_name}.{prop_name}. Skipping link.")
                continue

            # Find target in the GLOBAL registry
            registry_key = (target_class_name, target_base_id)
            target_individual = linking_context.get(registry_key)
            if not target_individual:
                 logger.warning(f"Link target {target_class_name} with ID '{target_base_id}' (from {lookup_method}) not found in global registry for relation {entity_name}.{prop_name}. Skipping link for {individual.name}.")
                 continue
            else:
                 logger.debug(f"Found link target {target_individual.name} for {entity_name}.{prop_name} via registry key {registry_key}.")

        elif link_context_key:
             # --- Link via Context Key (using CURRENT row's individuals) ---
             lookup_method = f"Context Key '{link_context_key}' (Row Lookup)"
             # Ensure individuals_in_row is provided and is a dictionary
             if not isinstance(individuals_in_row, dict):
                 logger.warning(f"Cannot link via context key '{link_context_key}' for {entity_name}.{prop_name}: individuals_in_row dictionary was not provided or invalid for row {row.get('row_num', 'N/A')}. Skipping link.")
                 continue

             target_individual = individuals_in_row.get(link_context_key)
             if not target_individual:
                 # Track missing context entity to log only once
                 missing_key = f"{link_context_key} for {entity_name}.{prop_name}"
                 if missing_key not in missing_context_entities:
                     missing_context_entities.add(missing_key)
                     logger.warning(f"Context entity '{link_context_key}' required for {entity_name}.{prop_name} not found in individuals_in_row dictionary for row {row.get('row_num', 'N/A')}. Skipping link.")
                 continue
             else:
                 logger.debug(f"Found link target {target_individual.name} for {entity_name}.{prop_name} via row context key '{link_context_key}'.")

        else:
            # Should not happen if parser validation is correct
            logger.error(f"Invalid mapping for object property {entity_name}.{prop_name}: Missing both 'column' and 'target_link_context'. Skipping.")
            continue

        # --- Type Check and Set Property ---
        if target_individual:
            target_cls = context.get_class(target_class_name)
            # Check if the found individual is an instance of the target class (or subclass)
            if not target_cls or not isinstance(target_individual, target_cls):
                 logger.error(f"Type mismatch for link {entity_name}.{prop_name}: Expected {target_class_name} but found target '{target_individual.name}' of type {type(target_individual).__name__} via {lookup_method}. Skipping link.")
                 continue

            # Set the property
            context.set_prop(individual, prop_name, target_individual)
            links_applied_count += 1
            
            # Add specific debug for important links
            if entity_name == "EventRecord":
                if prop_name == "involvesResource":
                    logger.debug(f"Successfully linked EventRecord {individual.name} to resource {target_individual.name} via {prop_name}")

    # logger.debug(f"Applied {links_applied_count} object property links for {entity_name} individual {individual.name}. Row {row.get('row_num', 'N/A')}.")


# --- DEPRECATED - Combined function (keep for reference temporarily?) ---
