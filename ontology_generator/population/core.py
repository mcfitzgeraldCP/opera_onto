"""
Core population module for the ontology generator.

This module provides the base functionality for ontology population, including the
PopulationContext class and property application functions.
"""
from typing import Dict, Any, Optional, List, Set, Tuple, Union

from owlready2 import (
    Ontology, Thing, ThingClass, PropertyClass,
    locstr, FunctionalProperty, ObjectProperty, DataProperty
)

from ontology_generator.utils.logging import pop_logger
from ontology_generator.config import XSD_TYPE_MAP
from ontology_generator.utils.types import safe_cast

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
        self.classes = defined_classes
        self.props = defined_properties
        self.is_functional = property_is_functional

    def get_class(self, name: str) -> Optional[ThingClass]:
        """
        Get a class by name.
        
        Args:
            name: The name of the class
            
        Returns:
            The class object or None if not found
        """
        cls = self.classes.get(name)
        if not cls: 
            pop_logger.error(f"Essential class '{name}' not found in defined_classes.")
        return cls

    def get_prop(self, name: str) -> Optional[PropertyClass]:
        """
        Get a property by name.
        
        Args:
            name: The name of the property
            
        Returns:
            The property object or None if not found
        """
        prop = self.props.get(name)
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
        if prop and individual:
            is_func = self.is_functional.get(prop_name, False)  # Default to non-functional if not specified
            _set_property_value(individual, prop, value, is_func)


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


def set_prop_if_col_exists(context: PopulationContext, 
                             individual: Thing, 
                             prop_name: str, 
                             col_name: str, 
                             row: Dict[str, Any], 
                             cast_func: callable, 
                             target_type: type, 
                             logger, 
                             default: Optional[Any] = None) -> None:
    """
    Safely sets a property value using the context, but only if the 
    corresponding column exists in the data row, logging an error otherwise.
    
    Args:
        context: The population context
        individual: The individual to set the property on
        prop_name: The name of the property to set
        col_name: The name of the column in the data row
        row: The data row dictionary
        cast_func: The casting function (e.g., safe_cast)
        target_type: The target type for casting
        logger: Logger object for logging errors
        default: Optional default value to pass to cast_func
    """
    if col_name not in row or row[col_name] is None or str(row[col_name]).strip() == '':
        logger.error(f"Missing required column '{col_name}' for property '{prop_name}' on individual '{individual.name}' in row: {context.row_to_string(row) if hasattr(context, 'row_to_string') else 'Row details unavailable'}")
        return
        
    try:
        # Prepare arguments for cast_func
        cast_args = [row.get(col_name), target_type]
        if default is not None:
            cast_args.append(default) # Append default only if provided
            
        value = cast_func(*cast_args)
        
        if value is not None:  # Don't set if casting resulted in None (unless default=None was intended)
            context.set_prop(individual, prop_name, value)
        elif default is not None and value is None: # Log if default was used but result is still None (unexpected from safe_cast typically)
             logger.debug(f"Casting column '{col_name}' for '{prop_name}' resulted in None even with default={default}")

    except Exception as e:
        logger.error(f"Error casting or setting property '{prop_name}' from column '{col_name}' on individual '{individual.name}': {e}")


def get_or_create_individual(onto_class: ThingClass, individual_name_base: Any, onto: Ontology, add_labels: Optional[List[str]] = None) -> Optional[Thing]:
    """
    Gets an individual if it exists, otherwise creates it.
    Uses a class-prefixed, sanitized name for the individual IRI. Returns None on failure.
    
    Args:
        onto_class: The class to create an individual of
        individual_name_base: The base name for the individual
        onto: The ontology to create the individual in
        add_labels: Optional list of labels to add to the individual
        
    Returns:
        The individual or None on failure
    """
    from ontology_generator.utils.types import sanitize_name
    
    if individual_name_base is None or str(individual_name_base).strip() == '':
        pop_logger.warning(f"Cannot get/create individual with empty base name for class {onto_class.name if onto_class else 'None'}")
        return None
    if not onto_class:
        pop_logger.error(f"Cannot get/create individual: onto_class parameter is None for base name '{individual_name_base}'.")
        return None

    # 1. Sanitize the base name
    safe_base = sanitize_name(individual_name_base)

    # 2. Create the class-specific, sanitized name
    final_name = f"{onto_class.name}_{safe_base}"

    # 3. Check if individual exists using namespace search
    individual = onto.search_one(iri=f"{onto.base_iri}{final_name}")

    if individual:
        # Check if the existing individual is of the correct type (or a subclass)
        if isinstance(individual, onto_class):
            # Optionally add labels even if retrieved
            if add_labels:
                current_labels = individual.label
                for lbl in add_labels:
                    lbl_str = safe_cast(lbl, str)
                    if lbl_str and lbl_str not in current_labels:
                            individual.label.append(lbl_str)
            return individual
        else:
            # This is a serious issue - IRI collision with different types
            pop_logger.error(f"IRI collision: Individual '{final_name}' ({individual.iri}) exists but is not of expected type {onto_class.name} (or its subclass). It has type(s): {individual.is_a}. Cannot proceed reliably for this individual.")
            # Decide how to handle: raise error, return None, or try alternative naming?
            # Raising an error might be safest to prevent corrupting the ontology.
            raise TypeError(f"IRI collision: {final_name} exists with incompatible type(s) {individual.is_a} (expected {onto_class.name}).")
            # return None # Alternative: Skip this individual

    # 4. Create the new individual
    try:
        pop_logger.debug(f"Creating new individual '{final_name}' of class {onto_class.name}")
        # Use the final_name directly - owlready2 handles IRI creation with the namespace
        new_individual = onto_class(final_name, namespace=onto)

        # Add labels if provided
        if add_labels:
            for lbl in add_labels:
                lbl_str = safe_cast(lbl, str)
                if lbl_str: new_individual.label.append(lbl_str)

        return new_individual
    except Exception as e:
        pop_logger.error(f"Failed to create individual '{final_name}' of class {onto_class.name}: {e}")
        return None


# --- In ontology_generator/population/core.py ---

# ... (keep apply_data_property_mappings and other functions as they are) ...

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
                 # This was the source of the original warnings
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

    # logger.debug(f"Applied {links_applied_count} object property links for {entity_name} individual {individual.name}. Row {row.get('row_num', 'N/A')}.")


# --- DEPRECATED - Combined function (keep for reference temporarily?) ---
