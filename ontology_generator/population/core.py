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
        
        # TKT-002: Track property usage and access patterns
        self._property_access_count = {prop_name: 0 for prop_name in defined_properties}
        self._property_usage_count = {prop_name: 0 for prop_name in defined_properties}
        self._property_misses = set()  # Track property names that were requested but not found
        self._individual_data_cache = {}  # Cache for storing data associated with individuals

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
        # TKT-009: Fix - Always track access counts even for properties that don't exist
        if name in self.defined_properties:
            self._property_access_count[name] = self._property_access_count.get(name, 0) + 1
        
        if name in self._property_cache:
            return self._property_cache[name]

        prop = self.defined_properties.get(name)
        if not prop:
            # TKT-002: Track property misses for later analysis
            self._property_misses.add(name)
            pop_logger.warning(f"TKT-002: Property '{name}' not found in defined properties.")
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
            
        # TKT-009: Fix - Track usage count only when we actually set the property value
        # Will be incremented inside _set_property_value when value is actually set
        
        is_functional = self.property_is_functional.get(prop_name, False) # Assume non-functional if not specified

        try:
            _set_property_value(individual, prop, value, is_functional, self)
        except Exception as e:
            pop_logger.error(f"Error setting property '{prop_name}' on individual '{individual.name}' with value '{value}': {e}", exc_info=True)
    
    # TKT-002: New method to store data associated with individuals for property access
    def store_individual_data(self, individual: Thing, data: Dict[str, Any]) -> None:
        """
        Store row data associated with an individual for later property lookups.
        
        Args:
            individual: The individual to associate with data
            data: Dictionary of column data that can be used for property lookup
        """
        if individual and hasattr(individual, "name"):
            self._individual_data_cache[individual.name] = data
    
    # TKT-002: New method to retrieve data associated with individuals
    def get_individual_data(self, individual: Thing) -> Optional[Dict[str, Any]]:
        """
        Retrieve data associated with an individual.
        
        Args:
            individual: The individual to get data for
            
        Returns:
            Dictionary of data associated with the individual or None
        """
        if individual and hasattr(individual, "name"):
            return self._individual_data_cache.get(individual.name)
        return None
    
    # TKT-002: New diagnostic method to report property usage statistics
    def report_property_usage(self) -> Dict[str, Dict[str, Any]]:
        """
        Generate a report of property usage statistics.
        
        Returns:
            Dictionary with property usage statistics
        """
        unused_properties = [
            prop_name for prop_name, count in self._property_usage_count.items() 
            if count == 0
        ]
        
        accessed_but_unused = [
            prop_name for prop_name in self.defined_properties
            if self._property_access_count.get(prop_name, 0) > 0 and 
               self._property_usage_count.get(prop_name, 0) == 0
        ]
        
        most_used = sorted(
            [(prop_name, count) for prop_name, count in self._property_usage_count.items() if count > 0],
            key=lambda x: x[1], 
            reverse=True
        )[:10]  # Top 10 most used properties
        
        report = {
            "total_properties": len(self.defined_properties),
            "total_accessed": len([p for p, c in self._property_access_count.items() if c > 0]),
            "total_used": len([p for p, c in self._property_usage_count.items() if c > 0]),
            "unused_count": len(unused_properties),
            "unused_properties": unused_properties,
            "accessed_but_unused": accessed_but_unused,
            "most_used": most_used,
            "property_misses": sorted(list(self._property_misses))
        }
        return report
    
    def log_property_usage_report(self) -> None:
        """
        Log property usage statistics at INFO level.
        """
        report = self.report_property_usage()
        
        pop_logger.info("TKT-002: Property Usage Report")
        pop_logger.info(f"  Total properties defined: {report['total_properties']}")
        pop_logger.info(f"  Properties accessed: {report['total_accessed']}/{report['total_properties']} ({report['total_accessed']/report['total_properties']*100:.1f}%)")
        pop_logger.info(f"  Properties used (set on individuals): {report['total_used']}/{report['total_properties']} ({report['total_used']/report['total_properties']*100:.1f}%)")
        
        if report['unused_count'] > 0:
            pop_logger.info(f"  Unused properties: {report['unused_count']} properties were never used")
            pop_logger.debug(f"  Unused property names: {', '.join(sorted(report['unused_properties'][:20]))}{' ...' if len(report['unused_properties']) > 20 else ''}")
        
        if report['accessed_but_unused']:
            pop_logger.warning(f"  TKT-002: {len(report['accessed_but_unused'])} properties were accessed but never successfully used: {', '.join(sorted(report['accessed_but_unused']))}")
        
        if report['property_misses']:
            pop_logger.warning(f"  TKT-002: {len(report['property_misses'])} undefined properties were requested: {', '.join(sorted(report['property_misses']))}")
        
        pop_logger.info(f"  Most used properties: {', '.join([f'{name} ({count})' for name, count in report['most_used'][:5]])}")


def _set_property_value(individual: Thing, prop: PropertyClass, value: Any, is_functional: bool, context: Optional[PopulationContext] = None) -> None:
    """
    Helper to set functional or non-functional properties, checking existence first.
    
    Args:
        individual: The individual to set the property on
        prop: The property to set
        value: The value to set
        is_functional: Whether the property is functional
        context: Optional PopulationContext to track property usage
    """
    if value is None: 
        return  # Don't set None values

    prop_name = prop.python_name  # Use Python name for attribute access
    original_prop_name = prop.name  # Store original name for tracking

    try:
        value_was_set = False  # Track if we actually set a value
        
        if is_functional:
            # Functional: Use setattr, potentially overwriting. Check if different first.
            current_value = getattr(individual, prop_name, None)
            # Handle comparison carefully, especially for complex types like lists/individuals
            # Simple direct comparison works for primitives and owlready individuals/locstr
            if current_value != value:
                setattr(individual, prop_name, value)
                pop_logger.debug(f"Set functional property {individual.name}.{prop.name} = {repr(value)}")
                value_was_set = True
        else:
            # Non-Functional: Use append, check if value already exists.
            # Initialize the attribute if it doesn't exist yet
            if not hasattr(individual, prop_name) or getattr(individual, prop_name) is None:
                # For non-functional properties, initialize with an empty list
                setattr(individual, prop_name, [])
            
            # Now safely append the value to the list
            current_values = getattr(individual, prop_name)
            # Check if value already exists to avoid duplicates
            if value not in current_values:
                current_values.append(value)
                pop_logger.debug(f"Appended non-functional property {individual.name}.{prop.name} = {repr(value)}")
                value_was_set = True

        # TKT-009: Fix - Track usage count only if we actually changed something
        if value_was_set and context is not None and hasattr(context, '_property_usage_count'):
            context._property_usage_count[original_prop_name] = context._property_usage_count.get(original_prop_name, 0) + 1

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
    
    # TKT-006: Add specific debug logging for AE model metrics
    ae_metrics = [
        'downtimeMinutes', 
        'runTimeMinutes', 
        'effectiveRuntimeMinutes',
        'goodProductionQuantity',
        'rejectProductionQuantity',
        'allMaintenanceTimeMinutes'
    ]
    
    if prop_name in ae_metrics:
        logger.debug(f"TKT-006: Successfully set AE model metric {prop_name} = {value} (from column {col_name}) on {individual.name}")
    
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
    # TKT-011: Check if this is trying to create a ProductionLineOrEquipment individual,
    # which should only be a structural class and not have direct instances
    if onto_class and onto_class.name == "ProductionLineOrEquipment":
        pop_logger.warning(f"Attempt to create individual of abstract class ProductionLineOrEquipment with base '{individual_name_base}'. This class should not have direct instances.")
        return None
        
    if not onto_class or not individual_name_base:
        pop_logger.error(f"Missing onto_class ({onto_class}) or individual_name_base ({individual_name_base}) for get_or_create.")
        return None

    # Sanitize the base name for use in IRI and registry key
    sanitized_name_base = sanitize_name(str(individual_name_base))
    if not sanitized_name_base:
        pop_logger.error(f"Could not sanitize base name '{individual_name_base}' for individual of class '{onto_class.name}'.")
        return None

    class_name_str = onto_class.name
    
    # Use the provided base identifier for the registry key
    # This follows the naming rules specified in the ticket
    registry_key = (class_name_str, sanitized_name_base)

    # Check registry first
    if registry_key in registry:
        existing_individual = registry[registry_key]
        pop_logger.debug(f"Found existing individual '{existing_individual.name}' (Key: {registry_key}) in registry.")
        # Add labels if found and labels provided
        if add_labels:
            for label in add_labels:
                if label and label not in existing_individual.label:
                    existing_individual.label.append(str(label))
        return existing_individual

    # --- If not found, create ---
    # Generate standardized IRI names based on class type
    individual_name = f"{class_name_str}_{sanitized_name_base}"

    try:
        # First, check if individual already exists in the ontology by full IRI
        # This is more reliable than partial matching with '*' wildcard
        existing_by_iri = onto.search_one(iri=f"{onto.base_iri}{individual_name}")
        
        # If not found by full IRI, try the more general search (backward compatibility)
        if not existing_by_iri:
            existing_by_iri = onto.search_one(iri=f"*{individual_name}")
            
        if existing_by_iri and isinstance(existing_by_iri, onto_class):
            # TKT-003: Add the individual to the registry and return it
            # This handles cases where individuals were created outside the registry
            pop_logger.debug(f"TKT-003: Individual with name '{individual_name}' already exists in ontology but not registry (Key: {registry_key}). Adding to registry and returning existing one.")
            registry[registry_key] = existing_by_iri
            
            # Add labels if provided
            if add_labels:
                for label in add_labels:
                    if label and label not in existing_by_iri.label:
                        existing_by_iri.label.append(str(label))
                        
            return existing_by_iri
        elif existing_by_iri:
            # Name collision with an individual of a DIFFERENT class - should be rare with prefixing
            pop_logger.error(f"Cannot create individual '{individual_name}': Name collision with existing individual '{existing_by_iri.name}' of different class ({type(existing_by_iri).__name__})")
            return None
            
        # If we get here, the individual doesn't exist yet - create it within onto context
        with onto:
            # Double-check again within context to ensure thread safety
            double_check = onto.search_one(iri=f"{onto.base_iri}{individual_name}")
            if double_check:
                # Another thread/process created it while we were checking
                if isinstance(double_check, onto_class):
                    pop_logger.debug(f"TKT-003: Race condition - individual '{individual_name}' was created between checks. Adding to registry and returning.")
                    registry[registry_key] = double_check
                    
                    # Add labels if provided
                    if add_labels:
                        for label in add_labels:
                            if label and label not in double_check.label:
                                double_check.label.append(str(label))
                                
                    return double_check
                else:
                    pop_logger.error(f"Race condition - individual with name '{individual_name}' was created between checks with incompatible class. Cannot proceed.")
                    return None
            
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
        # TKT-003: Skip properties with no column specified
        # These are programmatic/config properties like sequencePosition
        # that will be populated elsewhere (not from data rows)
        if 'column' not in details:
            logger.debug(f"Skipping programmatic/config property {entity_name}.{prop_name} - no column specified in mapping")
            continue
            
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
    individuals_in_row: Dict[str, Thing], # Individuals created/found specifically for THIS row in Pass 1
    exclude_structural: bool = False
) -> None:
    """Applies ONLY object property mappings, using linking_context or individuals_in_row to find targets."""
    if not mappings or 'object_properties' not in mappings:
        return

    obj_prop_mappings = mappings.get('object_properties', {})
    links_applied_count = 0
    
    # Define known structural properties that should be handled in post-processing
    structural_properties = ["isPartOfProductionLine", "hasEquipmentPart", "memberOfClass"]
    
    # Track missing entities per row to log only once
    missing_context_entities = set()

    for prop_name, details in obj_prop_mappings.items():
        # Skip structural properties if requested
        if exclude_structural and prop_name in structural_properties:
            logger.debug(f"Skipping structural property {entity_name}.{prop_name} for post-processing")
            continue
            
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
            else:
                # If missing both column and target_link_context, skip with a more specific message
                if not col_name and not link_context_key:
                    logger.debug(f"Skipping {entity_name}.{prop_name} in Pass 2 since it's handled in Pass 1 directly and missing column/target_link_context")
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

             # Added for TKT-002: Extra debugging for ProductionLine context lookups
             if entity_name == "Equipment" and prop_name == "isPartOfProductionLine":
                 logger.debug(f"Row {row.get('row_num', 'N/A')} - Equipment.isPartOfProductionLine context lookup - Available keys in individuals_in_row: {list(individuals_in_row.keys())}")
                 if "EQUIPMENT_TYPE" in row:
                     logger.debug(f"Row {row.get('row_num', 'N/A')} - EQUIPMENT_TYPE value in row: {row.get('EQUIPMENT_TYPE')}")

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
                # TKT-004: Add specific logging for event context relationships
                elif prop_name == "duringShift":
                    logger.info(f"Successfully linked EventRecord {individual.name} to Shift {target_individual.name} via context key '{link_context_key}'")
                elif prop_name == "occursDuring":
                    logger.info(f"Successfully linked EventRecord {individual.name} to TimeInterval {target_individual.name} via context key '{link_context_key}'")
                elif prop_name == "eventHasState":
                    logger.info(f"Successfully linked EventRecord {individual.name} to OperationalState {target_individual.name} via context key '{link_context_key}'")
                elif prop_name == "eventHasReason":
                    logger.info(f"Successfully linked EventRecord {individual.name} to OperationalReason {target_individual.name} via context key '{link_context_key}'")
            
            # Added for TKT-002: Track Equipment-Line links specifically
            if entity_name == "Equipment" and prop_name == "isPartOfProductionLine":
                logger.info(f"Successfully linking Equipment {individual.name} to Line {target_individual.name} via context key '{link_context_key}'")

    # logger.debug(f"Applied {links_applied_count} object property links for {entity_name} individual {individual.name}. Row {row.get('row_num', 'N/A')}.")


# --- DEPRECATED - Combined function (keep for reference temporarily?) ---
