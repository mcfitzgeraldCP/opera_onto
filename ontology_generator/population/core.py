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


def apply_property_mappings(individual: Thing, 
                           mappings: Dict[str, Dict[str, Dict[str, Any]]], 
                           row: Dict[str, Any],
                           context: PopulationContext, 
                           entity_name: str) -> None:
    """
    Apply property mappings to an individual based on the mappings dictionary.
    
    Args:
        individual: The individual to apply mappings to
        mappings: The property mappings dictionary for the entity
        row: The data row containing values
        context: The population context
        entity_name: The name of the entity (for logging)
    """
    # Process data properties from mappings
    for prop_name, prop_info in mappings.get("data_properties", {}).items():
        col_name = prop_info.get("column")
        data_type = prop_info.get("data_type")
        
        if col_name and data_type:
            # Special handling for localized strings
            if data_type == "xsd:string (with lang tag)":
                from ontology_generator.config import COUNTRY_TO_LANGUAGE, DEFAULT_LANGUAGE
                
                value_str = safe_cast(row.get(col_name), str)
                if value_str:
                    # Determine language tag
                    plant_country = safe_cast(row.get('PLANT_COUNTRY_DESCRIPTION'), str)
                    lang_tag = COUNTRY_TO_LANGUAGE.get(plant_country, DEFAULT_LANGUAGE) if plant_country else DEFAULT_LANGUAGE
                    
                    try:
                        # Create localized string
                        loc_value = locstr(value_str, lang=lang_tag)
                        context.set_prop(individual, prop_name, loc_value)
                        pop_logger.debug(f"Set localized property {entity_name}.{prop_name} from column '{col_name}' to '{value_str}'@{lang_tag}")
                    except Exception as e:
                        pop_logger.warning(f"Failed to create localized string for {entity_name}.{prop_name}: {e}")
                        # Fallback to regular string
                        context.set_prop(individual, prop_name, value_str)
            else:
                # Convert XSD type to Python type
                python_type = XSD_TYPE_MAP.get(data_type, str)
                
                # Get the value from the row data
                value = safe_cast(row.get(col_name), python_type)
                
                # Set the property if we have a valid value
                if value is not None:
                    context.set_prop(individual, prop_name, value)
                    pop_logger.debug(f"Set {entity_name}.{prop_name} from column '{col_name}' to {value}")
    
    # Process object properties from mappings
    for prop_name, prop_info in mappings.get("object_properties", {}).items():
        col_name = prop_info.get("column")
        target_class = prop_info.get("target_class")
        
        if col_name and target_class:
            # Get target class from population context
            tgt_class = context.get_class(target_class)
            if not tgt_class:
                pop_logger.warning(f"Target class '{target_class}' not found for object property {entity_name}.{prop_name}")
                continue
                
            # Get value from row
            value_id = safe_cast(row.get(col_name), str)
            if not value_id:
                continue
                
            # Create or get target individual
            target_individual = get_or_create_individual(tgt_class, value_id, context.onto, add_labels=[value_id])
            if target_individual:
                context.set_prop(individual, prop_name, target_individual)
                pop_logger.debug(f"Set object property {entity_name}.{prop_name} to {target_individual.name}")
                
    pop_logger.debug(f"Applied mappings for {entity_name}: {len(mappings.get('data_properties', {}))} data properties, {len(mappings.get('object_properties', {}))} object properties")
