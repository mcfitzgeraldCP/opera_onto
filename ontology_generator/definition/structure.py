"""
Ontology structure definition module for the ontology generator.

This module provides functions for defining the ontology structure.
"""
import re
import types
from typing import Dict, List, Tuple, Set, Optional, Any

from owlready2 import (
    Ontology, Thing, Nothing, ThingClass, PropertyClass,
    FunctionalProperty, InverseFunctionalProperty, TransitiveProperty,
    SymmetricProperty, AsymmetricProperty, ReflexiveProperty, IrreflexiveProperty,
    ObjectProperty, DataProperty
)

from ontology_generator.utils.logging import logger
from ontology_generator.config import (
    SPEC_PARENT_CLASS_COLUMN, XSD_TYPE_MAP,
    SPEC_COL_ENTITY, SPEC_COL_PROPERTY, SPEC_COL_PROP_TYPE,
    SPEC_COL_RAW_DATA, SPEC_COL_TARGET_RANGE, SPEC_COL_PROP_CHARACTERISTICS,
    SPEC_COL_INVERSE_PROPERTY, SPEC_COL_DOMAIN, SPEC_COL_TARGET_LINK_CONTEXT,
    SPEC_COL_PROGRAMMATIC, SPEC_COL_NOTES, SPEC_COL_ISA95_CONCEPT
)

def define_ontology_structure(onto: Ontology, specification: List[Dict[str, str]]) -> Tuple[Dict[str, ThingClass], Dict[str, PropertyClass], Dict[str, bool]]:
    """
    Defines OWL classes and properties based on the parsed specification.

    Args:
        onto: The ontology to define the structure in
        specification: The parsed specification
        
    Returns:
        tuple: (defined_classes, defined_properties, property_is_functional)
            - defined_classes: Dict mapping class name to owlready2 class object.
            - defined_properties: Dict mapping property name to owlready2 property object.
            - property_is_functional: Dict mapping property name to boolean indicating functionality.
    """
    logger.info(f"Defining ontology structure in: {onto.base_iri}")
    defined_classes: Dict[str, ThingClass] = {}
    defined_properties: Dict[str, PropertyClass] = {}
    property_is_functional: Dict[str, bool] = {}  # Track which properties are functional based on spec
    class_metadata: Dict[str, Dict[str, Any]] = {} # Store metadata like notes per class
    
    # TKT-002: Track all property names in the specification
    spec_property_names = set()
    spec_property_types = {} # Store property types for validation
    
    # --- Pre-process Spec for Class Metadata and Hierarchy ---
    logger.debug("--- Pre-processing specification for class details ---")
    all_class_names: Set[str] = set()
    class_parents: Dict[str, str] = {} # {child_name: parent_name}
    
    # TKT-002: Pre-process property names from specification
    for row in specification:
        prop_name = row.get(SPEC_COL_PROPERTY, '').strip()
        if prop_name:
            spec_property_names.add(prop_name)
            spec_property_types[prop_name] = row.get(SPEC_COL_PROP_TYPE, '').strip()
    
    logger.info(f"TKT-002: Found {len(spec_property_names)} unique properties in specification")
    
    for i, row in enumerate(specification):
        class_name = row.get(SPEC_COL_ENTITY, '').strip()
        if class_name:
            all_class_names.add(class_name)
            # Store metadata (using first encountered row for simplicity, could collect all)
            if class_name not in class_metadata:
                    class_metadata[class_name] = {
                        'notes': row.get(SPEC_COL_NOTES, ''),
                        'isa95': row.get(SPEC_COL_ISA95_CONCEPT, ''),
                        'row_index': i # For reference if needed
                    }
            # Store parent class info if column exists
            parent_name = row.get(SPEC_PARENT_CLASS_COLUMN, '').strip()
            if parent_name and parent_name != class_name: # Avoid self-parenting
                class_parents[class_name] = parent_name
                all_class_names.add(parent_name) # Ensure parent is also considered a class


    # --- Pass 1: Define Classes with Hierarchy ---
    logger.debug("--- Defining Classes ---")
    with onto:
        # Ensure Thing is available if not explicitly listed
        if "Thing" not in all_class_names and "owl:Thing" not in all_class_names:
            pass # Thing is implicitly available via owlready2

        defined_order: List[str] = [] # Track definition order for hierarchy
        definition_attempts = 0
        max_attempts = len(all_class_names) + 5 # Allow some leeway for complex hierarchies

        classes_to_define: Set[str] = set(cn for cn in all_class_names if cn.lower() != "owl:thing") # Exclude Thing variants

        while classes_to_define and definition_attempts < max_attempts:
            defined_in_pass: Set[str] = set()
            for class_name in sorted(list(classes_to_define)): # Sort for somewhat deterministic order
                parent_name = class_parents.get(class_name)
                parent_class_obj: ThingClass = Thing # Default parent is Thing

                if parent_name:
                    if parent_name == "Thing" or parent_name.lower() == "owl:thing": # Handle case variation
                        parent_class_obj = Thing
                    elif parent_name in defined_classes:
                        parent_class_obj = defined_classes[parent_name]
                    else:
                        # Parent not defined yet, skip this class for now
                        logger.debug(f"Deferring class '{class_name}', parent '{parent_name}' not defined yet.")
                        continue

                # Define the class
                try:
                    if class_name not in defined_classes:
                        logger.debug(f"Attempting to define Class: {class_name} with Parent: {parent_class_obj.name}")
                        # Ensure class name is valid Python identifier if needed by backend
                        safe_class_name = re.sub(r'\W|^(?=\d)', '_', class_name)
                        if safe_class_name != class_name:
                            logger.warning(f"Class name '{class_name}' sanitized to '{safe_class_name}' for internal use. Using original name for IRI.")
                            # Sticking with original name as owlready2 often handles non-standard chars in IRIs

                        # Revert to types.new_class
                        new_class: ThingClass = types.new_class(class_name, (parent_class_obj,))

                        defined_classes[class_name] = new_class
                        defined_order.append(class_name)
                        defined_in_pass.add(class_name)
                        logger.debug(f"Defined Class: {new_class.iri} (Parent: {parent_class_obj.iri})") # Removed the extra type check log

                        # Add annotations like comments/labels from pre-processed metadata
                        meta = class_metadata.get(class_name)
                        if meta:
                            comments = []
                            if meta['notes']: comments.append(f"Notes: {meta['notes']}")
                            if meta['isa95']: comments.append(f"ISA-95 Concept: {meta['isa95']}")
                            if comments:
                                new_class.comment = comments
                                logger.debug(f"Added comments to class {class_name}")

                except Exception as e:
                    logger.error(f"Error defining class '{class_name}' with parent '{getattr(parent_class_obj,'name','N/A')}': {e}")
                    # Let it retry, might be a transient issue or solvable in later pass

            classes_to_define -= defined_in_pass
            definition_attempts += 1
            if not defined_in_pass and classes_to_define:
                logger.error(f"Could not define remaining classes (possible circular dependency or missing parents): {classes_to_define}")
                break # Avoid infinite loop

        if classes_to_define:
            logger.warning(f"Failed to define the following classes: {classes_to_define}")

    # --- Pass 2: Define Properties ---
    logger.debug("--- Defining Properties ---")
    properties_to_process = [row for row in specification if row.get(SPEC_COL_PROPERTY)]
    temp_inverse_map: Dict[str, str] = {} # Stores {prop_name: inverse_name}

    # Define instance-level equipment sequence properties if not in specification
    with onto:
        # Define instance-level sequence properties for Equipment
        if defined_classes.get("Equipment") and "sequencePosition" not in defined_properties:
            logger.info("Adding instance-level equipment sequence properties")
            
            # Get Equipment class
            cls_Equipment = defined_classes.get("Equipment")
            cls_ProductionLine = defined_classes.get("ProductionLine")
            cls_EquipmentClass = defined_classes.get("EquipmentClass")
            
            if not cls_Equipment:
                logger.error("Equipment class not found. Cannot define instance-level sequence properties.")
            else:
                # 1. sequencePosition (DataProperty)
                # TKT-001: Fix - Create property instance directly
                with onto:
                    class sequencePosition(DataProperty, FunctionalProperty):
                        domain = [cls_Equipment]
                        range = [int]
                        comment = ["Position of equipment instance in production sequence"]
                
                defined_properties["sequencePosition"] = onto.sequencePosition
                property_is_functional["sequencePosition"] = True
                logger.info("Defined property: sequencePosition")
                
                # 2. isImmediatelyUpstreamOf (ObjectProperty) with its inverse
                if cls_Equipment:
                    # TKT-001: Fix - Create property instance directly
                    with onto:
                        class isImmediatelyUpstreamOf(ObjectProperty):
                            domain = [cls_Equipment]
                            range = [cls_Equipment]
                            comment = ["Links to the immediate downstream equipment in sequence"]
                    
                    defined_properties["isImmediatelyUpstreamOf"] = onto.isImmediatelyUpstreamOf
                    property_is_functional["isImmediatelyUpstreamOf"] = False
                    logger.info("Defined property: isImmediatelyUpstreamOf")
                    
                    # Define inverse
                    # TKT-001: Fix - Create property instance directly
                    with onto:
                        class isImmediatelyDownstreamOf(ObjectProperty):
                            domain = [cls_Equipment]
                            range = [cls_Equipment]
                            comment = ["Links to the immediate upstream equipment in sequence"]
                    
                    defined_properties["isImmediatelyDownstreamOf"] = onto.isImmediatelyDownstreamOf
                    property_is_functional["isImmediatelyDownstreamOf"] = False
                    logger.info("Defined property: isImmediatelyDownstreamOf")
                    
                    # Set inverses
                    onto.isImmediatelyUpstreamOf.inverse_property = onto.isImmediatelyDownstreamOf
                    onto.isImmediatelyDownstreamOf.inverse_property = onto.isImmediatelyUpstreamOf
                
                # 3. isPartOfProductionLine (ObjectProperty)
                if cls_Equipment and cls_ProductionLine:
                    # TKT-001: Fix - Create property instance directly
                    with onto:
                        class isPartOfProductionLine(ObjectProperty):
                            domain = [cls_Equipment]
                            range = [cls_ProductionLine]
                            comment = ["Links equipment to its production line"]
                    
                    defined_properties["isPartOfProductionLine"] = onto.isPartOfProductionLine
                    property_is_functional["isPartOfProductionLine"] = False
                    logger.info("Defined property: isPartOfProductionLine")
                
                # 4. memberOfClass (ObjectProperty)
                if cls_Equipment and cls_EquipmentClass:
                    # TKT-001: Fix - Create property instance directly
                    with onto:
                        class memberOfClass(ObjectProperty, FunctionalProperty):
                            domain = [cls_Equipment]
                            range = [cls_EquipmentClass]
                            comment = ["Links equipment instance to its equipment class"]
                    
                    defined_properties["memberOfClass"] = onto.memberOfClass
                    property_is_functional["memberOfClass"] = True
                    logger.info("Defined property: memberOfClass")
                    
            # TKT-001: Define equipmentClassId property for EquipmentClass if it doesn't exist
            if defined_classes.get("EquipmentClass") and "equipmentClassId" not in defined_properties:
                logger.info("Adding missing equipmentClassId property for EquipmentClass")
                
                cls_EquipmentClass = defined_classes.get("EquipmentClass")
                
                # TKT-001: Fix - Create property instance directly
                with onto:
                    class equipmentClassId(DataProperty, FunctionalProperty):
                        domain = [cls_EquipmentClass]
                        range = [str]
                        comment = ["Identifier for the equipment class"]
                
                defined_properties["equipmentClassId"] = onto.equipmentClassId
                property_is_functional["equipmentClassId"] = True
                logger.info("Defined property: equipmentClassId")

    with onto:
        # Define properties first without inverse, handle inverse in a second pass
        for row in properties_to_process:
            prop_name = row.get(SPEC_COL_PROPERTY,'').strip()
            if not prop_name or prop_name in defined_properties:
                continue # Skip empty or already defined properties
                
            # Skip deprecated class-level sequence properties
            if prop_name in ["classIsUpstreamOf", "classIsDownstreamOf", "defaultSequencePosition"]:
                logger.info(f"Skipping deprecated class-level property: {prop_name}")
                continue
            
            # TKT-008: Skip redundant definition of instance-level sequence properties
            # Since we already define these above if needed, just continue when they appear in the spec
            if prop_name in ["sequencePosition", "isImmediatelyUpstreamOf", "isImmediatelyDownstreamOf",
                             "isPartOfProductionLine", "memberOfClass"]:
                logger.debug(f"Skipping duplicate definition of instance-level property: {prop_name}")
                continue
                
            prop_type_str = row.get(SPEC_COL_PROP_TYPE, '').strip()
            domain_str = row.get(SPEC_COL_DOMAIN, '').strip()
            range_str = row.get(SPEC_COL_TARGET_RANGE, '').strip()
            characteristics_str = row.get(SPEC_COL_PROP_CHARACTERISTICS, '').strip().lower() # Normalize
            inverse_prop_name = row.get(SPEC_COL_INVERSE_PROPERTY, '').strip()

            if not prop_type_str or not domain_str or not range_str:
                logger.warning(f"Skipping property '{prop_name}' due to missing type, domain, or range in spec.")
                continue

            # TKT-001: Fix - Set up parent classes for property creation
            parent_classes = []
            base_prop_type = None
            if prop_type_str == 'ObjectProperty':
                base_prop_type = ObjectProperty
                parent_classes.append(ObjectProperty)
            elif prop_type_str in ['DataProperty', 'DatatypeProperty']:  # Accept both
                base_prop_type = DataProperty
                parent_classes.append(DataProperty)
            else:
                logger.warning(f"Unknown property type '{prop_type_str}' for property '{prop_name}'. Skipping.")
                continue

            # Add characteristics
            is_functional = 'functional' in characteristics_str
            property_is_functional[prop_name] = is_functional  # Track functionality status
            
            if is_functional: 
                parent_classes.append(FunctionalProperty)
            if 'inversefunctional' in characteristics_str: 
                parent_classes.append(InverseFunctionalProperty)
            if 'transitive' in characteristics_str: 
                parent_classes.append(TransitiveProperty)
            if 'symmetric' in characteristics_str: 
                parent_classes.append(SymmetricProperty)
            if 'asymmetric' in characteristics_str: 
                parent_classes.append(AsymmetricProperty)
            if 'reflexive' in characteristics_str: 
                parent_classes.append(ReflexiveProperty)
            if 'irreflexive' in characteristics_str: 
                parent_classes.append(IrreflexiveProperty)

            try:
                # TKT-001: Fix - Create property directly using owlready2 proper mechanisms
                with onto:
                    # Create property class based on the base type
                    if base_prop_type is ObjectProperty:
                        # For ObjectProperty
                        if is_functional:
                            class_def = types.new_class(prop_name, (ObjectProperty, FunctionalProperty))
                        else:
                            class_def = types.new_class(prop_name, (ObjectProperty,))
                        
                        # Add other characteristics if needed
                        characteristics = []
                        if 'inversefunctional' in characteristics_str: characteristics.append(InverseFunctionalProperty)
                        if 'transitive' in characteristics_str: characteristics.append(TransitiveProperty)
                        if 'symmetric' in characteristics_str: characteristics.append(SymmetricProperty)
                        if 'asymmetric' in characteristics_str: characteristics.append(AsymmetricProperty)
                        if 'reflexive' in characteristics_str: characteristics.append(ReflexiveProperty)
                        if 'irreflexive' in characteristics_str: characteristics.append(IrreflexiveProperty)
                        
                        if characteristics:
                            # Update bases if more characteristics are needed
                            new_bases = list(class_def.__bases__)
                            new_bases.extend(characteristics)
                            class_def.__bases__ = tuple(new_bases)
                            
                    elif base_prop_type is DataProperty:
                        # For DataProperty
                        if is_functional:
                            class_def = types.new_class(prop_name, (DataProperty, FunctionalProperty))
                        else:
                            class_def = types.new_class(prop_name, (DataProperty,))
                    
                    # Store the property in our registry
                    new_prop = class_def

                # Set Domain
                domain_class_names = [dc.strip() for dc in domain_str.split('|')]
                prop_domain = []
                valid_domain_found = False
                for dc_name in domain_class_names:
                    domain_class = defined_classes.get(dc_name)
                    if domain_class:
                        prop_domain.append(domain_class)
                        valid_domain_found = True
                    elif dc_name == "Thing" or dc_name.lower() == "owl:thing": # Allow Thing as domain
                        prop_domain.append(Thing)
                        valid_domain_found = True
                    else:
                        logger.warning(f"Domain class '{dc_name}' not found for property '{prop_name}'.")

                if prop_domain:
                    new_prop.domain = prop_domain # Assign list directly for union domain
                    logger.debug(f"Set domain for {prop_name} to {[dc.name for dc in prop_domain]}")
                elif not valid_domain_found:
                    logger.warning(f"No valid domain classes found for property '{prop_name}'. Skipping domain assignment.")

                # Set Range
                if base_prop_type is ObjectProperty:
                    range_class_names = [rc.strip() for rc in range_str.split('|')]
                    prop_range = []
                    valid_range_found = False
                    for rc_name in range_class_names:
                        range_class = defined_classes.get(rc_name)
                        if range_class:
                            prop_range.append(range_class)
                            valid_range_found = True
                        elif rc_name == "Thing" or rc_name.lower() == "owl:thing": # Allow Thing as range
                            prop_range.append(Thing)
                            valid_range_found = True
                        else:
                            logger.warning(f"Range class '{rc_name}' not found for object property '{prop_name}'.")
                    if prop_range:
                        new_prop.range = prop_range # Assign list directly for union range
                        logger.debug(f"Set range for {prop_name} to {[rc.name for rc in prop_range]}")
                    elif not valid_range_found:
                        logger.warning(f"Could not set any valid range for object property '{prop_name}'.")

                elif base_prop_type is DataProperty:
                    target_type = XSD_TYPE_MAP.get(range_str)
                    if target_type:
                        new_prop.range = [target_type]
                        logger.debug(f"Set range for {prop_name} to {target_type.__name__ if hasattr(target_type, '__name__') else target_type}")
                    else:
                        logger.warning(f"Unknown XSD type '{range_str}' for property '{prop_name}'. Skipping range assignment.")

                # Add annotations
                notes = row.get(SPEC_COL_NOTES, '')
                isa95 = row.get(SPEC_COL_ISA95_CONCEPT, '')
                comments = []
                if notes: comments.append(f"Notes: {notes}")
                if isa95: comments.append(f"ISA-95 Concept: {isa95}")
                if comments:
                    new_prop.comment = comments

                defined_properties[prop_name] = new_prop
                logger.debug(f"Defined Property: {new_prop.iri} of type {prop_type_str} with characteristics {', '.join([p.__name__ for p in parent_classes[1:]]) if len(parent_classes) > 1 else 'None'}")

                # Store inverse relationship for later processing
                if inverse_prop_name and base_prop_type is ObjectProperty:
                    temp_inverse_map[prop_name] = inverse_prop_name

            except Exception as e:
                logger.error(f"Error defining property '{prop_name}': {e}")

    # --- Pass 3: Set Inverse Properties ---
    logger.debug("--- Setting Inverse Properties ---")
    with onto: # Ensure changes are applied within the ontology context
        for prop_name, inverse_name in temp_inverse_map.items():
            prop = defined_properties.get(prop_name)
            inverse_prop = defined_properties.get(inverse_name)

            if prop and inverse_prop:
                try:
                    # Check if already set to the desired value to avoid unnecessary writes/warnings if possible
                    current_inverse = getattr(prop, "inverse_property", None)
                    if current_inverse != inverse_prop:
                        prop.inverse_property = inverse_prop
                        logger.debug(f"Set inverse_property for {prop.name} to {inverse_prop.name}")
                    # Also explicitly set the inverse's inverse property back
                    current_inverse_of_inverse = getattr(inverse_prop, "inverse_property", None)
                    if current_inverse_of_inverse != prop:
                        inverse_prop.inverse_property = prop
                        logger.debug(f"Set inverse_property for {inverse_prop.name} back to {prop.name}")
                except Exception as e:
                    logger.error(f"Error setting inverse property between '{prop_name}' and '{inverse_name}': {e}")
            elif not prop:
                logger.warning(f"Property '{prop_name}' not found while trying to set inverse '{inverse_name}'.")
            elif not inverse_prop:
                logger.warning(f"Inverse property '{inverse_name}' not found for property '{prop_name}'.")

    # TKT-002: Verify all properties from spec were defined
    missing_properties = spec_property_names - set(defined_properties.keys())
    
    # Exclude properties we intentionally skip
    excluded_properties = {"classIsUpstreamOf", "classIsDownstreamOf", "defaultSequencePosition"}
    real_missing = missing_properties - excluded_properties
    
    if real_missing:
        logger.warning(f"TKT-002: {len(real_missing)} properties in specification were not defined: {', '.join(sorted(real_missing))}")
    else:
        logger.info(f"TKT-002: All properties from specification were successfully defined")
    
    # Check for property type consistency
    for prop_name, prop_obj in defined_properties.items():
        if prop_name in spec_property_types:
            expected_type = spec_property_types[prop_name]
            # TKT-002: Fix - Use isinstance() or issubclass() to check property types correctly
            if expected_type == 'ObjectProperty' and not (isinstance(prop_obj, ObjectProperty) or issubclass(prop_obj, ObjectProperty)):
                logger.warning(f"TKT-002: Property '{prop_name}' is not an instance of ObjectProperty as specified")
            elif expected_type in ['DataProperty', 'DatatypeProperty'] and not (isinstance(prop_obj, DataProperty) or issubclass(prop_obj, DataProperty)):
                logger.warning(f"TKT-002: Property '{prop_name}' is not an instance of DataProperty as specified")
    
    # Log total property counts
    object_props = [p for p in defined_properties.values() if isinstance(p, ObjectProperty)]
    data_props = [p for p in defined_properties.values() if isinstance(p, DataProperty)]
    logger.info(f"TKT-002: Defined {len(defined_properties)} total properties ({len(object_props)} object properties, {len(data_props)} data properties)")
    
    logger.info("Ontology structure definition complete.")
    return defined_classes, defined_properties, property_is_functional

def create_selective_classes(onto: Ontology, 
                          specification: List[Dict[str, str]], 
                          skip_classes: List[str] = None,
                          strict_adherence: bool = False) -> Dict[str, ThingClass]:
    """
    Creates only the necessary classes from the specification, 
    optionally skipping specified classes or enforcing strict spec adherence.
    
    Args:
        onto: The ontology object
        specification: Parsed specification
        skip_classes: List of class names to skip (won't be created)
        strict_adherence: If True, only create classes explicitly defined in spec
        
    Returns:
        Dict mapping class name to class object
    """
    logger.info(f"Creating classes selectively from specification")
    
    skip_classes = set(skip_classes or [])
    defined_classes = {}
    
    # Pre-process spec to find essential classes
    spec_classes = set()
    spec_parents = {}
    property_domains = set()
    property_ranges = set()
    
    for row in specification:
        # Get class names
        class_name = row.get(SPEC_COL_ENTITY, '').strip()
        if class_name:
            spec_classes.add(class_name)
            parent_name = row.get(SPEC_PARENT_CLASS_COLUMN, '').strip()
            if parent_name and parent_name != class_name:
                spec_parents[class_name] = parent_name
                spec_classes.add(parent_name)  # Ensure parent is in spec classes
        
        # Get property domains and ranges
        prop_name = row.get(SPEC_COL_PROPERTY, '').strip()
        if prop_name:
            # Get domains
            domain_str = row.get(SPEC_COL_DOMAIN, '').strip()
            if domain_str:
                domains = [d.strip() for d in domain_str.split('|')]
                property_domains.update(domains)
            
            # Get ranges for object properties
            prop_type = row.get(SPEC_COL_PROP_TYPE, '').strip()
            if prop_type == 'ObjectProperty':
                range_str = row.get(SPEC_COL_TARGET_RANGE, '').strip()
                if range_str:
                    ranges = [r.strip() for r in range_str.split('|')]
                    property_ranges.update(ranges)
    
    # Determine which classes to create
    classes_to_create = set()
    
    if strict_adherence:
        # Only create classes explicitly defined in spec
        classes_to_create = spec_classes
    else:
        # Create spec classes plus any referenced in properties
        classes_to_create = spec_classes | property_domains | property_ranges
    
    # Remove classes to skip
    classes_to_create -= skip_classes
    
    # Create classes with proper hierarchy
    with onto:
        # First pass: create all classes as direct subclasses of Thing
        for class_name in classes_to_create:
            if class_name == "Thing" or class_name.lower() == "owl:thing":
                continue  # Skip Thing
            
            try:
                # Create as subclass of Thing initially
                new_class = types.new_class(class_name, (Thing,))
                defined_classes[class_name] = new_class
                logger.debug(f"Created class {class_name} (temp parent: Thing)")
            except Exception as e:
                logger.error(f"Error creating class {class_name}: {e}")
        
        # Second pass: set proper parent classes
        for class_name, class_obj in defined_classes.items():
            parent_name = spec_parents.get(class_name)
            if parent_name and parent_name in defined_classes:
                parent_class = defined_classes[parent_name]
                # Reset parent
                class_obj.is_a = [parent_class]
                logger.debug(f"Set parent of {class_name} to {parent_name}")
    
    classes_skipped = spec_classes - set(defined_classes.keys())
    if classes_skipped:
        logger.info(f"Skipped {len(classes_skipped)} classes: {', '.join(sorted(classes_skipped))}")
    
    logger.info(f"Selectively created {len(defined_classes)} classes from specification")
    return defined_classes
