"""
Sequence relationship module for the ontology generator.

This module provides functions for setting up equipment sequence relationships.
"""
from typing import Dict, Any, List, Optional, Tuple

from owlready2 import Thing, Ontology, ThingClass, PropertyClass

from ontology_generator.utils.logging import pop_logger
from ontology_generator.population.core import PopulationContext, _set_property_value
from ontology_generator.config import DEFAULT_EQUIPMENT_SEQUENCE, LINE_SPECIFIC_EQUIPMENT_SEQUENCE

def _safe_sort_by_position(items, default_position=999999):
    """
    Safely sorts items by position value, handling None values gracefully.
    
    Args:
        items: Dictionary items (key, value) where value might be None
        default_position: Default value to use for None positions
        
    Returns:
        Sorted list of (key, value) tuples
    """
    def get_safe_position(item):
        key, position = item
        if position is None:
            pop_logger.warning(f"Found None position for {key}, using default position {default_position} for sorting")
            return default_position
        return position
        
    return sorted(items, key=get_safe_position)

def setup_equipment_sequence_relationships(onto: Ontology,
                                           equipment_class_positions: Dict[str, int],
                                           defined_classes: Dict[str, ThingClass],
                                           defined_properties: Dict[str, PropertyClass],
                                           created_equipment_class_inds: Dict[str, Thing]):
    """
    Establish upstream/downstream relationships between equipment *classes* based on sequence positions.
    """
    pop_logger.info("Setting up CLASS-LEVEL equipment sequence relationships based on position...")

    # Get context for properties/classes
    context = PopulationContext(onto, defined_classes, defined_properties, {}) # is_functional map not needed here

    # Get the CLASS-LEVEL properties
    prop_classIsUpstreamOf = context.get_prop("classIsUpstreamOf")
    prop_classIsDownstreamOf = context.get_prop("classIsDownstreamOf") # Optional for inverse

    if not prop_classIsUpstreamOf:
        pop_logger.error("Cannot establish CLASS-LEVEL sequence relationships: 'classIsUpstreamOf' property not defined.")
        return
    if not prop_classIsDownstreamOf:
        pop_logger.warning("'classIsDownstreamOf' inverse property not found. Only forward class relationships will be set.")

    cls_EquipmentClass = context.get_class("EquipmentClass")
    if not cls_EquipmentClass: return # Should have been caught earlier, but safe check

    # Verify domain/range compatibility (optional but good practice)
    if cls_EquipmentClass not in prop_classIsUpstreamOf.domain:
        pop_logger.warning(f"Property 'classIsUpstreamOf' ({prop_classIsUpstreamOf}) does not have EquipmentClass in its domain {prop_classIsUpstreamOf.domain}.")
    # Range check assumes list of classes is expected
    if not any(issubclass(cls_EquipmentClass, r_cls) for r_cls in (prop_classIsUpstreamOf.range if isinstance(prop_classIsUpstreamOf.range, list) else [prop_classIsUpstreamOf.range])):
        pop_logger.warning(f"Property 'classIsUpstreamOf' ({prop_classIsUpstreamOf}) does not have EquipmentClass in its range {prop_classIsUpstreamOf.range}.")


    if not created_equipment_class_inds:
        pop_logger.warning("No created EquipmentClass individuals provided. Cannot establish class relationships.")
        return
    if not equipment_class_positions:
        pop_logger.warning("Equipment class positions dictionary is empty. Cannot establish class relationships.")
        return

    # Sort classes by their position number
    sorted_classes = sorted(equipment_class_positions.items(), key=lambda item: item[1])

    if len(sorted_classes) < 2:
        pop_logger.warning("Not enough equipment classes with sequence positions (< 2) to establish relationships.")
        return

    # Create relationships based on sequence order
    relationships_created = 0
    with onto:
        for i in range(len(sorted_classes) - 1):
            upstream_class_name, up_pos = sorted_classes[i]
            downstream_class_name, down_pos = sorted_classes[i + 1]

            upstream_ind = created_equipment_class_inds.get(upstream_class_name)
            downstream_ind = created_equipment_class_inds.get(downstream_class_name)

            if not upstream_ind:
                pop_logger.warning(f"Sequence setup: Upstream class individual '{upstream_class_name}' not found in provided dict.")
                continue
            if not downstream_ind:
                pop_logger.warning(f"Sequence setup: Downstream class individual '{downstream_class_name}' not found in provided dict.")
                continue

            pop_logger.debug(f"Evaluating CLASS relationship: {upstream_ind.name} (Pos {up_pos}) -> {downstream_ind.name} (Pos {down_pos})")

            # Set relationships (classIsUpstreamOf is NON-functional per spec)
            try:
                # Use helper to check if relationship already exists before appending
                _set_property_value(upstream_ind, prop_classIsUpstreamOf, downstream_ind, is_functional=False)

                # Explicitly set the inverse relationship if available and needed
                if prop_classIsDownstreamOf:
                    _set_property_value(downstream_ind, prop_classIsDownstreamOf, upstream_ind, is_functional=False)

                # Check if the forward relationship was actually added (or already existed)
                if downstream_ind in getattr(upstream_ind, prop_classIsUpstreamOf.python_name, []):
                    relationships_created += 1 # Count successful links (new or existing is fine)
                    pop_logger.debug(f"Confirmed CLASS relationship: {upstream_class_name} classIsUpstreamOf {downstream_class_name}")

            except Exception as e:
                pop_logger.error(f"Error setting class relationship {upstream_class_name} -> {downstream_class_name}: {e}")

    pop_logger.info(f"Established/verified {relationships_created} CLASS-LEVEL upstream relationships.")

    # Print relationship summary to stdout
    print("\n=== EQUIPMENT CLASS SEQUENCE RELATIONSHIP REPORT ===")
    if relationships_created > 0:
        print(f"Established/verified {relationships_created} upstream relationships between Equipment Classes:")
        # Re-iterate to print the established sequence
        for i in range(len(sorted_classes) - 1):
            upstream_class_name, _ = sorted_classes[i]
            downstream_class_name, _ = sorted_classes[i + 1]
            # Check if both individuals exist to avoid errors if one was missing during linking
            if created_equipment_class_inds.get(upstream_class_name) and created_equipment_class_inds.get(downstream_class_name):
                print(f"  {upstream_class_name} → {downstream_class_name}")
    else:
        print("No class-level sequence relationships were created or verified.")
    print(f"Total classes with positions considered: {len(sorted_classes)}")

def setup_equipment_instance_relationships(onto: Ontology,
                                          defined_classes: Dict[str, ThingClass],
                                          defined_properties: Dict[str, PropertyClass],
                                          property_is_functional: Dict[str, bool],
                                          equipment_class_positions: Dict[str, int]):
    """
    Establish upstream/downstream relationships between equipment *instances* within the same production line.
    
    The approach:
    1. Group equipment instances by production line
    2. For each line:
        a. Determine equipment class sequence positions using line-specific or default configuration
        b. Assign sequencePosition to each Equipment instance based on its class's position
        c. Sort instances on the line by sequencePosition and then by equipmentId (for same position)
        d. Link sorted instances with isImmediatelyUpstreamOf/isImmediatelyDownstreamOf relationships
    
    Args:
        onto: The ontology
        defined_classes: Dictionary of defined classes
        defined_properties: Dictionary of defined properties
        property_is_functional: Dictionary indicating whether properties are functional
        equipment_class_positions: Dictionary mapping equipment class names to sequence positions
    """
    pop_logger.info("Setting up INSTANCE-LEVEL equipment relationships within production lines...")

    # Get context for properties/classes
    context = PopulationContext(onto, defined_classes, defined_properties, property_is_functional)

    # Get the required classes and properties
    cls_Equipment = context.get_class("Equipment")
    cls_ProductionLine = context.get_class("ProductionLine")
    cls_EquipmentClass = context.get_class("EquipmentClass")
    
    # Get instance-level properties
    prop_isPartOfProductionLine = context.get_prop("isPartOfProductionLine")
    prop_memberOfClass = context.get_prop("memberOfClass")
    prop_equipmentClassId = context.get_prop("equipmentClassId")
    prop_equipmentId = context.get_prop("equipmentId")
    prop_sequencePosition = context.get_prop("sequencePosition")
    prop_isImmediatelyUpstreamOf = context.get_prop("isImmediatelyUpstreamOf")
    prop_isImmediatelyDownstreamOf = context.get_prop("isImmediatelyDownstreamOf")

    # Check essentials
    required_components = [
        cls_Equipment, cls_ProductionLine, cls_EquipmentClass,
        prop_isPartOfProductionLine, prop_memberOfClass, prop_equipmentClassId,
        prop_equipmentId, prop_sequencePosition, prop_isImmediatelyUpstreamOf
    ]
    
    missing_components = [name for i, name in enumerate([
        "Equipment", "ProductionLine", "EquipmentClass",
        "isPartOfProductionLine", "memberOfClass", "equipmentClassId",
        "equipmentId", "sequencePosition", "isImmediatelyUpstreamOf"
    ]) if not required_components[i]]
    
    if missing_components:
        pop_logger.error(f"Missing required components for equipment sequencing: {', '.join(missing_components)}")
        return

    if not prop_isImmediatelyDownstreamOf:
        pop_logger.warning("'isImmediatelyDownstreamOf' inverse property not found. Only forward instance relationships will be set.")

    if not equipment_class_positions:
        pop_logger.warning("Equipment class positions dictionary is empty. Cannot establish instance relationships.")
        return
        
    # Log the equipment class positions for better diagnostics
    pop_logger.info(f"Equipment class positions from configuration (total: {len(equipment_class_positions)}):")
    for class_name, position in sorted(equipment_class_positions.items(), key=lambda x: (x[1] if x[1] is not None else 999999)):
        pop_logger.info(f"  • Class '{class_name}': Position {position}")

    # Group equipment instances by line
    pop_logger.debug("Grouping equipment instances by production line...")
    line_equipment_map: Dict[Thing, List[Thing]] = {}  # {line_individual: [equipment_instances]}
    
    # Track lines with equipment but no sequence
    lines_without_sequence: List[str] = []

    # Count totals for diagnostic tracking
    total_equipment_processed = 0
    total_equipment_with_class = 0
    total_equipment_with_line = 0
    
    # Step 1: Group all Equipment instances by ProductionLine
    for equipment_inst in onto.search(type=cls_Equipment):
        total_equipment_processed += 1
        
        # Get the line(s) this equipment belongs to
        equipment_lines = getattr(equipment_inst, prop_isPartOfProductionLine.python_name, [])
        if not equipment_lines:
            pop_logger.debug(f"Equipment {equipment_inst.name} is not linked to any ProductionLine. Skipping.")
            continue
        
        total_equipment_with_line += 1
        
        # Get the EquipmentClass this equipment belongs to
        equipment_class_ind = getattr(equipment_inst, prop_memberOfClass.python_name, None)
        
        # More detailed logging when missing EquipmentClass link
        if not equipment_class_ind:
            eq_id = getattr(equipment_inst, prop_equipmentId.python_name, equipment_inst.name)
            pop_logger.warning(f"Equipment {eq_id} has no memberOfClass relationship. Skipping for sequence setup.")
            continue
        
        if not isinstance(equipment_class_ind, cls_EquipmentClass):
            eq_id = getattr(equipment_inst, prop_equipmentId.python_name, equipment_inst.name)
            pop_logger.warning(f"Equipment {eq_id} linked to non-EquipmentClass '{equipment_class_ind}'. Skipping for sequence setup.")
            continue
        
        total_equipment_with_class += 1
        
        # Add equipment to each of its production lines
        for line in equipment_lines:
            if not isinstance(line, cls_ProductionLine):
                pop_logger.warning(f"Equipment {equipment_inst.name} linked to non-ProductionLine '{line}'. Skipping this link.")
                continue
            
            if line not in line_equipment_map:
                line_equipment_map[line] = []
            
            line_equipment_map[line].append(equipment_inst)
    
    # Log summary of equipment distribution for diagnosis
    pop_logger.info(f"Equipment distribution summary:")
    pop_logger.info(f"  • Total equipment found: {total_equipment_processed}")
    pop_logger.info(f"  • Equipment linked to lines: {total_equipment_with_line}")
    pop_logger.info(f"  • Equipment linked to equipment classes: {total_equipment_with_class}")
    pop_logger.info(f"  • Production lines with equipment: {len(line_equipment_map)}")
    
    # Process each line to establish equipment instance relationships
    total_relationships = 0
    line_relationship_counts: Dict[str, int] = {}
    
    def safe_get_equipment_id(equipment: Thing) -> str:
        """Helper to safely get equipmentId or fallback to name for sorting."""
        equipment_id = getattr(equipment, prop_equipmentId.python_name, None)
        if equipment_id:
            return str(equipment_id)
        return equipment.name
    
    with onto:
        for line_ind, equipment_instances in line_equipment_map.items():
            line_id = getattr(line_ind, "lineId", line_ind.name)
            pop_logger.info(f"Processing equipment instance relationships for line: {line_id}")
            
            if not equipment_instances:
                pop_logger.debug(f"No equipment instances found for line: {line_id}")
                continue
            
            # Step 2: Get sequence configuration for this line
            # Check for line-specific sequence configuration first
            line_specific_sequence = LINE_SPECIFIC_EQUIPMENT_SEQUENCE.get(line_id)
            
            if line_specific_sequence:
                pop_logger.info(f"Using line-specific sequence configuration for line {line_id}")
                sequence_config = line_specific_sequence
                # Log the line-specific sequence
                pos_str = ", ".join([f"{cls}:{pos}" for cls, pos in sorted(sequence_config.items(), key=lambda x: x[1])])
                pop_logger.info(f"Line-specific sequence for {line_id}: {pos_str}")
            else:
                # Use the default global sequence
                pop_logger.info(f"Using default sequence configuration for line {line_id}")
                sequence_config = DEFAULT_EQUIPMENT_SEQUENCE
            
            # Step 3: Assign sequencePosition to each Equipment instance based on its class position
            equipment_with_positions = []
            equipment_without_positions = []
            
            for equipment_inst in equipment_instances:
                eq_id = safe_get_equipment_id(equipment_inst)
                
                # Get the EquipmentClass this equipment belongs to
                equipment_class_ind = getattr(equipment_inst, prop_memberOfClass.python_name, None)
                if not equipment_class_ind:
                    pop_logger.warning(f"Equipment {eq_id} has no memberOfClass. Skipping sequence assignment.")
                    equipment_without_positions.append((equipment_inst, "no_class_link"))
                    continue
                
                # Get the class name string from the EquipmentClass individual
                class_name = getattr(equipment_class_ind, prop_equipmentClassId.python_name, None)
                if not class_name:
                    # Try to get the name directly from the individual
                    class_name = equipment_class_ind.name
                    if class_name.startswith("EquipmentClass_"):
                        class_name = class_name[len("EquipmentClass_"):]
                    pop_logger.warning(f"EquipmentClass {equipment_class_ind.name} has no equipmentClassId. Using name {class_name} as fallback.")
                
                # If still no class name, skip this equipment
                if not class_name:
                    pop_logger.warning(f"Cannot determine class name for {eq_id}. Skipping sequence assignment.")
                    equipment_without_positions.append((equipment_inst, "no_class_name"))
                    continue
                
                # Find position from sequence configuration
                position = sequence_config.get(class_name)
                
                if position is None:
                    # Try fallback to global sequence if using line-specific but not found
                    if line_specific_sequence and class_name in DEFAULT_EQUIPMENT_SEQUENCE:
                        position = DEFAULT_EQUIPMENT_SEQUENCE.get(class_name)
                        pop_logger.info(f"Using fallback global position {position} for class {class_name} on line {line_id}")
                
                if position is not None:
                    # Set the sequencePosition on the Equipment instance
                    try:
                        context.set_prop(equipment_inst, "sequencePosition", position)
                        pop_logger.debug(f"Set sequencePosition={position} on Equipment {eq_id} (class: {class_name})")
                        equipment_with_positions.append((equipment_inst, position, eq_id))
                    except Exception as e:
                        pop_logger.error(f"Error setting sequencePosition={position} on Equipment {eq_id}: {e}")
                        equipment_without_positions.append((equipment_inst, "set_position_error"))
                else:
                    pop_logger.warning(f"No sequence position found for class {class_name} on line {line_id}")
                    equipment_without_positions.append((equipment_inst, f"no_position_for_class_{class_name}"))
            
            # Step 4: Sort equipment instances by position, then by equipmentId
            sorted_equipment = sorted(equipment_with_positions, key=lambda x: (x[1], x[2]))
            
            if not sorted_equipment:
                pop_logger.warning(f"No equipment with sequence positions found on line {line_id}. Skipping relationship setup.")
                lines_without_sequence.append(line_id)
                continue
            
            # Log the sorted equipment for verification
            pop_logger.info(f"Sorted equipment on line {line_id} (format: id [position]):")
            for i, (eq, pos, eq_id) in enumerate(sorted_equipment):
                pop_logger.info(f"  {i+1}. {eq_id} [{pos}]")
            
            # Step 5: Link equipment instances with isImmediatelyUpstreamOf/isImmediatelyDownstreamOf
            relationships_created = 0
            for i in range(len(sorted_equipment) - 1):
                upstream_eq, _, up_id = sorted_equipment[i]
                downstream_eq, _, down_id = sorted_equipment[i + 1]
                
                # Validate to ensure we're not creating self-references
                if upstream_eq is downstream_eq:
                    pop_logger.error(f"Detected self-reference attempt for equipment {up_id} on line {line_id}. Skipping this link.")
                    continue
                
                try:
                    # Check if the relationship already exists to avoid duplicates
                    downstream_list = getattr(upstream_eq, prop_isImmediatelyUpstreamOf.python_name, [])
                    if not isinstance(downstream_list, list):
                        downstream_list = [downstream_list] if downstream_list else []
                    
                    if downstream_eq in downstream_list:
                        pop_logger.debug(f"Relationship already exists: {up_id} isImmediatelyUpstreamOf {down_id}")
                    else:
                        # Create forward relationship
                        _set_property_value(upstream_eq, prop_isImmediatelyUpstreamOf, downstream_eq, is_functional=False)
                        pop_logger.debug(f"Created forward relationship: {up_id} isImmediatelyUpstreamOf {down_id}")
                    
                    # Create inverse relationship if property exists
                    if prop_isImmediatelyDownstreamOf:
                        upstream_list = getattr(downstream_eq, prop_isImmediatelyDownstreamOf.python_name, [])
                        if not isinstance(upstream_list, list):
                            upstream_list = [upstream_list] if upstream_list else []
                        
                        if upstream_eq in upstream_list:
                            pop_logger.debug(f"Inverse relationship already exists: {down_id} isImmediatelyDownstreamOf {up_id}")
                        else:
                            _set_property_value(downstream_eq, prop_isImmediatelyDownstreamOf, upstream_eq, is_functional=False)
                            pop_logger.debug(f"Created inverse relationship: {down_id} isImmediatelyDownstreamOf {up_id}")
                    
                    relationships_created += 1
                except Exception as e:
                    pop_logger.error(f"Error creating relationship between {up_id} and {down_id}: {e}")
            
            # Record relationships for this line
            if relationships_created > 0:
                line_relationship_counts[line_id] = relationships_created
                total_relationships += relationships_created
                pop_logger.info(f"Established {relationships_created} instance relationships for line {line_id}.")
            
            # Log info about equipment without positions
            if equipment_without_positions:
                # Group by reason for diagnostic purposes
                reason_groups = {}
                for eq, reason in equipment_without_positions:
                    if reason not in reason_groups:
                        reason_groups[reason] = []
                    reason_groups[reason].append(safe_get_equipment_id(eq))
                
                # Log the grouped reasons
                pop_logger.warning(f"Line {line_id} has {len(equipment_without_positions)} equipment without positions:")
                for reason, ids in reason_groups.items():
                    pop_logger.warning(f"  • Reason '{reason}': {len(ids)} equipment - {', '.join(ids[:5])}" + 
                                       (f" and {len(ids)-5} more" if len(ids) > 5 else ""))

    # Print summary report
    print("\n=== EQUIPMENT INSTANCE RELATIONSHIP REPORT ===")
    if total_relationships > 0:
        pop_logger.info(f"Established {total_relationships} equipment instance relationships across {len(line_relationship_counts)} production lines.")
        print(f"Established {total_relationships} equipment instance relationships on {len(line_relationship_counts)} lines:")
        for line_id, count in sorted(line_relationship_counts.items()):
            print(f"  Line {line_id}: {count} relationships")

        # Print info about the sequencing approach
        print("\nInstance sequencing approach:")
        print("  • Each Equipment instance is assigned a sequencePosition based on its EquipmentClass")
        print("  • Equipment instances are sorted by sequencePosition, then by equipmentId")
        print("  • Sorted instances are linked via isImmediatelyUpstreamOf/isImmediatelyDownstreamOf")
        print("  • Sequence configuration is determined by:")
        print("    - Line-specific configuration (if available in LINE_SPECIFIC_EQUIPMENT_SEQUENCE)")
        print("    - Global DEFAULT_EQUIPMENT_SEQUENCE configuration (fallback)")
    else:
        pop_logger.warning("No equipment instance relationships were established.")
        print("No equipment instance relationships could be established.")
        print("Possible reasons:")
        print("  • Equipment not linked to lines/classes")
        print("  • Missing sequence positions for equipment classes")
        print("  • No equipment found on the same line")
        
    # Log lines without sequence
    if lines_without_sequence:
        print("\nProduction lines without sequence relationships:")
        for line_id in sorted(lines_without_sequence):
            print(f"  • {line_id}")

    return total_relationships  # Return count of created relationships for tracking
